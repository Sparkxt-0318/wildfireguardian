"""Burnout window, D4 symmetry, wind canonicalization and the structured model."""
import math

import torch
from torch.nn import functional as F

from wildfire.burnout import FlamingWindow, source_weight
from wildfire.canonical import (
    D4_ELEMENTS, canonical_kernels, d4_kernel, d4_sample, d4_spatial, d4_symmetrize_kernels, d4_wind,
    offset_rotation_matrix,
)
from wildfire.meanfield import propagate_mean_field
from wildfire.models import (
    StructuredKernelModel, anderson_length_to_breadth, elliptical_template, new_burn_probability,
)


def test_cell_older_than_residence_contributes_only_smoulder_multiplier():
    window = FlamingWindow(residence_hours=3.0, smoulder=0.25)
    initial = torch.tensor([[[[1.0, 1.0]]]], dtype=torch.float64)
    ages = torch.tensor([[[[1.0, 5.0]]]], dtype=torch.float64)
    source = window.source(initial, ages, [], clock_hours=0.0)
    assert source.flatten().tolist() == [1.0, 0.25]
    # The young cell crosses the residence after two more hours.
    later = window.source(initial, ages, [], clock_hours=2.5)
    assert later.flatten().tolist() == [0.25, 0.25]
    # Increments ignite at their step midpoint.
    increment = torch.tensor([[[[0.0, 0.5]]]], dtype=torch.float64)
    history = [(0.5, increment)]
    mixed = window.source(torch.zeros_like(initial), torch.zeros_like(ages), history, clock_hours=3.0)
    assert mixed.flatten().tolist() == [0.0, 0.5]
    mixed = window.source(torch.zeros_like(initial), torch.zeros_like(ages), history, clock_hours=4.0)
    assert mixed.flatten().tolist() == [0.0, 0.125]
    assert float(source_weight(torch.tensor(10.0), 3.0, 1.0)) == 1.0


def test_burnout_mean_field_equals_absorbing_with_unit_multiplier():
    kernels = torch.rand(1, 9, 5, 5, dtype=torch.float64, generator=torch.Generator().manual_seed(2))
    kernels[:, 4] = 0

    class Provider:
        def kernel_rates(self, environment, feature_valid=None, *, boundary="zero"):
            return kernels

    p0 = torch.zeros(1, 1, 5, 5, dtype=torch.float64)
    p0[..., 2, 2] = 1
    env = torch.zeros(1, 1, 5, 5, dtype=torch.float64)
    absorbing = propagate_mean_field(Provider(), p0, env, [1.0] * 3)
    unit = propagate_mean_field(Provider(), p0, env, [1.0] * 3, burnout=FlamingWindow(1.0, 1.0))
    assert torch.allclose(absorbing.burned_probability, unit.burned_probability, rtol=0, atol=1e-15)
    burned_out = propagate_mean_field(Provider(), p0, env, [1.0] * 3, burnout=FlamingWindow(1.0, 0.0),
                                      initial_age_hours=torch.full_like(p0, 5.0))
    assert torch.allclose(burned_out.burned_probability[-1], p0)


def test_d4_wind_is_physical_and_group_closed():
    u, v = torch.tensor(1.0), torch.tensor(0.0)  # toward east
    assert d4_wind(u, v, 1, False) == (0.0, 1.0)  # quarter turn counterclockwise: toward north
    assert d4_wind(u, v, 0, True) == (-1.0, 0.0)  # mirror: toward west
    x = torch.arange(12.0).reshape(1, 3, 4)
    for k, flip in D4_ELEMENTS:
        moved = d4_spatial(x, k, flip)
        assert torch.equal(torch.flip(torch.rot90(moved, -k, (-2, -1)), (-1,)) if flip
                           else torch.rot90(moved, -k, (-2, -1)), x)
    # A wind arrow drawn on the map rotates with the map.
    field = torch.zeros(1, 5, 5)
    field[0, 2, 3] = 1  # one cell east of the centre
    rotated = d4_spatial(field, 1, False)
    assert float(rotated[0, 1, 2]) == 1  # now one cell north of the centre


def test_symmetrized_constant_generator_is_d4_equivariant():
    g = torch.Generator().manual_seed(4)
    logits = torch.randn(1, 9, 1, 1, generator=g, dtype=torch.float64)

    def constant(environment):
        rates = F.softplus(logits).expand(environment.shape[0], -1, *environment.shape[-2:]).clone()
        rates[:, 4] = 0
        return rates

    environment = torch.zeros(1, 2, 7, 6, dtype=torch.float64)
    burned = (torch.rand(1, 1, 7, 6, generator=g) < 0.3).double()
    kernels = d4_symmetrize_kernels(constant, environment)
    reference = new_burn_probability(burned, kernels, boundary="zero").probability
    for k, flip in D4_ELEMENTS:
        moved_env = d4_spatial(environment, k, flip)
        moved_kernels = d4_symmetrize_kernels(constant, moved_env)
        assert torch.allclose(moved_kernels, d4_kernel(kernels, k, flip), rtol=0, atol=1e-12)
        prediction = new_burn_probability(d4_spatial(burned, k, flip), moved_kernels, boundary="zero").probability
        assert torch.allclose(prediction, d4_spatial(reference, k, flip), rtol=0, atol=1e-12)
    # Without symmetrization a generic constant kernel is not equivariant.
    plain = constant(environment)
    turned = new_burn_probability(d4_spatial(burned, 1, False), constant(d4_spatial(environment, 1, False)),
                                  boundary="zero").probability
    assert not torch.allclose(turned, d4_spatial(new_burn_probability(burned, plain, boundary="zero").probability, 1, False))


def test_d4_sample_moves_wind_values():
    environment = torch.zeros(3, 4, 4)
    environment[0] = 2.0  # u
    environment[1] = 0.0  # v
    environment[2, 0, 0] = 7.0  # scalar landmark
    moved, labels = d4_sample(environment, (0, 1), 1, False, torch.eye(4)[None])
    assert torch.allclose(moved[0], torch.zeros(4, 4)) and torch.allclose(moved[1], torch.full((4, 4), 2.0))
    assert float(moved[2, 3, 0]) == 7.0
    assert labels.shape == (1, 4, 4)


def test_offset_rotation_quarter_turn_matches_d4_offsets():
    kernel = torch.arange(25.0, dtype=torch.float64).reshape(1, 25, 1, 1)
    matrix = offset_rotation_matrix(5, math.pi / 2)
    rotated = torch.einsum("ij,njhw->nihw", matrix, kernel)
    assert torch.allclose(rotated, d4_kernel(kernel, 1, False), atol=1e-12)


def test_canonical_kernels_identity_at_zero_angle_and_rotation_of_constant():
    g = torch.Generator().manual_seed(8)
    logits = torch.randn(1, 9, 1, 1, generator=g, dtype=torch.float64)

    def constant(environment):
        return F.softplus(logits).expand(environment.shape[0], -1, *environment.shape[-2:])

    clean = torch.randn(1, 2, 6, 6, generator=g, dtype=torch.float64)
    assert torch.equal(canonical_kernels(constant, clean, 0.0, 3), constant(clean))
    turned = canonical_kernels(constant, clean, math.pi / 2, 3)
    expected = d4_kernel(constant(clean), 1, False)
    assert torch.allclose(turned[..., 2:4, 2:4], expected[..., 2:4, 2:4], atol=1e-9)


def test_anderson_ratio_and_template_orientation():
    assert torch.isclose(anderson_length_to_breadth(torch.tensor(0.0)), torch.tensor(1.0), atol=1e-3)
    assert float(anderson_length_to_breadth(torch.tensor(10.0))) > 2
    u = torch.full((1, 1, 1, 1), 10.0)
    v = torch.zeros((1, 1, 1, 1))
    template = elliptical_template(u, v, 3, torch.tensor(1.0)).reshape(3, 3)
    # Wind toward east: a target receives most from the source on its west (dx = -1).
    assert float(template[1, 0]) > float(template[1, 2])
    calm = elliptical_template(torch.zeros_like(u), v, 3, torch.tensor(1.0)).reshape(3, 3)
    assert torch.allclose(calm, calm.flip(0)) and torch.allclose(calm, calm.flip(1))


def test_structured_model_variants_produce_valid_kernels():
    names = ["weather.wind_eastward_10m", "weather.wind_northward_10m", "terrain.slope_degrees"]
    environment = torch.randn(2, 3, 12, 11)
    burned = torch.zeros(2, 1, 12, 11)
    burned[..., 6, 5] = 1
    for prior in ("free", "ellipse"):
        for frame in ("none", "d4", "wind"):
            torch.manual_seed(0)
            model = StructuredKernelModel(3, 5, 4, channel_names=names, prior=prior, frame=frame,
                                          residence_hours=3.0, spotting_radius=7)
            model.initialize_rate(0.05)
            kernels = model.kernel_rates(environment, boundary="zero")
            assert kernels.shape == (2, 25, 12, 11)
            assert bool(torch.isfinite(kernels).all()) and bool((kernels >= 0).all())
            assert bool((kernels[:, 12] == 0).all())
            result = model(burned, environment, boundary="zero")
            assert bool(result.valid.all())
            spot = model.spot_rate(burned, environment)
            assert spot.shape == burned.shape and bool((spot >= 0).all())
