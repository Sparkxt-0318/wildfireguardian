"""Public plotting selection, masking, probability, and event contracts."""
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest
import torch

from wildfire.plotting import _matrix, plot_comparison, plot_matrix


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def test_import_does_not_load_matplotlib_or_torch():
    script = "import sys; import wildfire.plotting; assert 'matplotlib' not in sys.modules; assert 'torch' not in sys.modules"
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)


def test_selection_preserves_masks_nonfinite_values_and_full_shape_validity():
    values = np.arange(24, dtype=float).reshape(2, 1, 3, 4)
    values[1, 0, 0, 0] = np.nan
    values[1, 0, 0, 1] = np.inf
    own_mask = np.zeros_like(values, dtype=bool)
    own_mask[1, 0, 1, 1] = True
    valid = np.ones_like(values, dtype=bool)
    valid[1, 0, 2, 2] = False
    original = np.ma.array(values, mask=own_mask)
    selected = _matrix(original, valid, index=1)
    expected = np.array([[True, True, False, False], [False, True, False, False], [False, False, True, False]])
    np.testing.assert_array_equal(selected.mask, expected)
    np.testing.assert_array_equal(original.mask, own_mask)
    np.testing.assert_array_equal(valid.sum(), 23)


def test_singleton_dimensions_and_negative_indices():
    values = np.arange(24).reshape(2, 1, 3, 4)
    np.testing.assert_array_equal(_matrix(values, index=-1), values[1, 0])
    np.testing.assert_array_equal(_matrix(values, index=(1, 0)), values[1, 0])
    np.testing.assert_array_equal(_matrix(values[:1]), values[0, 0])
    np.testing.assert_array_equal(_matrix(values[0, 0], index=()), values[0, 0])


def test_cpu_tensor_with_grad_and_bfloat16_conversion():
    tensor = torch.arange(12, dtype=torch.float32).reshape(1, 3, 4).requires_grad_()
    np.testing.assert_array_equal(_matrix(tensor), tensor.detach().numpy()[0])
    bfloat = tensor.detach().to(torch.bfloat16)
    np.testing.assert_array_equal(_matrix(bfloat), tensor.detach().numpy()[0])
    assert tensor.requires_grad


def test_tensor_conversion_detaches_and_copies_to_cpu_before_numpy():
    class ResidentTensor:
        def __init__(self):
            self.calls = []

        def detach(self):
            self.calls.append("detach")
            return self

        def cpu(self):
            self.calls.append("cpu")
            return self

        def numpy(self):
            assert self.calls == ["detach", "cpu"]
            self.calls.append("numpy")
            return np.array([[0.5]])

    value = ResidentTensor()
    np.testing.assert_array_equal(_matrix(value), [[0.5]])
    assert value.calls == ["detach", "cpu", "numpy"]


@pytest.mark.parametrize("shape,index", [((2, 3, 4), None), ((1, 2, 3, 4), 0), ((0, 3, 4), None)])
def test_ambiguous_leading_dimensions_require_selection(shape, index):
    with pytest.raises(ValueError, match="ambiguous"):
        _matrix(np.zeros(shape), index=index)


@pytest.mark.parametrize("index", [True, [0], (slice(None),), (0.5,), (True,)])
def test_indices_are_explicit_integers(index):
    with pytest.raises(TypeError, match="index"):
        _matrix(np.zeros((2, 3, 4)), index=index)


def test_indices_cannot_select_spatial_axes_or_out_of_bounds():
    with pytest.raises(ValueError, match="leading dimensions"):
        _matrix(np.ones((3, 4)), index=0)
    with pytest.raises(ValueError, match="leading dimensions"):
        _matrix(np.ones((2, 3, 4)), index=(0, 0))
    with pytest.raises(IndexError, match="out of bounds"):
        _matrix(np.ones((2, 3, 4)), index=2)


@pytest.mark.parametrize("value", [np.ones((2, 2), dtype=complex), np.array([["1", "2"]]), np.array([[1, 2]], dtype=object)])
def test_matrix_rejects_nonreal_or_nonnumeric_arrays(value):
    with pytest.raises(TypeError, match="real numeric"):
        _matrix(value)


@pytest.mark.parametrize("value", [np.array(1), np.ones(3), np.ones((0, 3)), np.ones((3, 0))])
def test_matrix_requires_nonempty_two_dimensional_spatial_data(value):
    with pytest.raises(ValueError):
        _matrix(value)


def test_validity_is_boolean_and_full_shape_without_broadcasting():
    values = np.zeros((2, 1, 3, 4))
    with pytest.raises(TypeError, match="booleans"):
        _matrix(values, np.ones_like(values), index=0)
    with pytest.raises(ValueError, match="full matrix shape"):
        _matrix(values, np.ones((3, 4), dtype=bool), index=0)
    valid = np.ma.array(np.ones((3, 4), dtype=bool), mask=False)
    valid.mask[1, 2] = True
    assert _matrix(values[0, 0], valid).mask[1, 2]


def test_matrix_uses_existing_axes_imshow_options_and_colorbar_label():
    figure, ax = plt.subplots()
    returned, result = plot_matrix([[1, 2], [3, np.nan]], ax=ax, title="Heat",
                                  cmap="magma", vmin=0, vmax=5, origin="lower",
                                  colorbar_label="kW/m²", aspect="auto")
    assert returned is figure and result is ax
    assert ax.get_title() == "Heat"
    assert ax.images[0].get_clim() == (0, 5)
    assert ax.images[0].origin == "lower"
    assert ax.images[0].get_array().mask[1, 1]
    assert figure.axes[1].get_ylabel() == "kW/m²"
    np.testing.assert_allclose(ax.images[0].cmap.get_bad(), matplotlib.colors.to_rgba("#d9d9d9"))
    figure.canvas.draw()


def test_matrix_can_omit_colorbar_and_plot_all_unknown():
    figure, ax = plot_matrix(np.full((3, 4), np.nan), colorbar=False)
    assert len(figure.axes) == 1
    assert np.ma.getmaskarray(ax.images[0].get_array()).all()
    figure.canvas.draw()


def comparison_values():
    probability = np.array([[0.0, 0.2, np.nan], [0.6, 0.9, 1.0]])
    observed = np.array([[0.0, 1.0, 1.0], [1.0, np.nan, 0.0]])
    return probability, observed


@pytest.mark.parametrize("mode,count", [("both", 3), ("side_by_side", 2), ("overlay", 1)])
def test_modes_panel_counts_probability_scale_legends_and_headless_render(mode, count, tmp_path):
    figure, axes = plot_comparison(*comparison_values(), mode=mode)
    assert isinstance(axes, np.ndarray) and axes.shape == (count,)
    assert len(figure.axes) == count + 1
    for ax in axes:
        assert ax.images[0].get_clim() == (0, 1)
        assert any("unavailable" in text.get_text().lower() for text in ax.get_legend().get_texts())
    assert figure.axes[-1].get_ylabel() == "New-burn probability q"
    destination = tmp_path / f"{mode}.png"
    figure.savefig(destination)
    assert destination.stat().st_size > 1000


def test_side_panels_and_overlay_keep_independent_probability_and_event_masks():
    probability, observed = comparison_values()
    valid = np.array([[True, True, True], [False, True, True]])
    figure, axes = plot_comparison(probability, observed, valid=valid, mode="both", colorbar=False)
    np.testing.assert_array_equal(axes[0].images[0].get_array().mask, [[False, False, False], [False, True, False]])
    np.testing.assert_array_equal(axes[1].images[0].get_array().mask, [[False, False, True], [True, False, False]])
    np.testing.assert_array_equal(axes[2].images[0].get_array().mask, [[False, False, True], [True, False, False]])
    np.testing.assert_array_equal(axes[2].collections[0].get_offsets(), [[1, 0], [2, 0], [0, 1]])
    np.testing.assert_allclose(np.ma.getdata(axes[1].images[0].get_array()), probability, equal_nan=True)
    assert len(figure.axes) == 3


@pytest.mark.parametrize("index", [0, 1])
def test_unavailable_legends_describe_only_the_selected_displayed_matrix(index):
    probability = np.full((2, 1, 2, 3), 0.25)
    observed = np.zeros_like(probability)
    probability[1, 0, 0, 0] = np.nan
    observed[0, 0, 1, 1] = np.nan
    _, axes = plot_comparison(probability, observed, index=index, mode="both", colorbar=False)
    for panel, ax in enumerate(axes):
        labels = {text.get_text() for text in ax.get_legend().get_texts()}
        expected_unknown = index == (0 if panel == 0 else 1)
        expected_label = "Reference unavailable" if panel == 0 else "Probability unavailable"
        assert (expected_label in labels) == expected_unknown
        assert np.ma.getmaskarray(ax.images[0].get_array()).any() == expected_unknown
        np.testing.assert_allclose(ax.images[0].cmap.get_bad(), matplotlib.colors.to_rgba("#d9d9d9"))


def test_overlay_does_not_threshold_probability_or_fabricate_events():
    probability = np.array([[0.0, 0.999], [0.01, 1.0]])
    observed = np.array([[1, 0], [1, 0]])
    _, axes = plot_comparison(probability, observed, mode="overlay", colorbar=False)
    np.testing.assert_array_equal(axes[0].images[0].get_array(), probability)
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[0, 0], [0, 1]])


def test_default_next_hour_markers_are_hollow_so_probability_remains_visible_inside():
    probability = np.array([[0.1, 0.2], [0.3, 0.8]])
    observed = np.array([[0, 0], [0, 1]])
    figure, axes = plot_comparison(
        probability, observed, burned_area=np.array([[1, 0], [0, 0]]), colorbar=False,
    )
    ax = axes[0]
    marker = ax.collections[0]
    facecolors = marker.get_facecolors()
    assert facecolors.size == 0 or np.all(facecolors[:, 3] == 0)
    np.testing.assert_allclose(marker.get_edgecolors(), [matplotlib.colors.to_rgba("#00e5ff")])
    assert np.all(marker.get_linewidths() > 0)
    np.testing.assert_array_equal(marker.get_offsets(), [[1, 1]])
    # The actual event outline leaves the q=0.8 probability cell unchanged;
    # the prior-burn raster also remains transparent at this new-burn cell.
    np.testing.assert_array_equal(ax.images[0].get_array(), probability)
    assert ax.images[0].get_array()[1, 1] == 0.8
    assert np.ma.getmaskarray(ax.images[1].get_array())[1, 1]
    event_handles = [handle for handle in ax.get_legend().legend_handles
                     if isinstance(handle, matplotlib.lines.Line2D)]
    assert len(event_handles) == 1
    assert event_handles[0].get_markerfacecolor() == "none"
    np.testing.assert_allclose(matplotlib.colors.to_rgba(event_handles[0].get_markeredgecolor()),
                               matplotlib.colors.to_rgba("#00e5ff"))
    figure.canvas.draw()


def test_next_hour_markers_can_use_an_explicit_filled_face_color():
    probability = np.array([[0.25, 0.75]])
    figure, axes = plot_comparison(
        probability, [[1, 0]], marker_facecolor="red", event_color="blue", colorbar=False,
    )
    marker = axes[0].collections[0]
    np.testing.assert_allclose(marker.get_facecolors(), [matplotlib.colors.to_rgba("red")])
    np.testing.assert_allclose(marker.get_edgecolors(), [matplotlib.colors.to_rgba("blue")])
    np.testing.assert_array_equal(axes[0].images[0].get_array(), probability)
    event_handles = [handle for handle in axes[0].get_legend().legend_handles
                     if isinstance(handle, matplotlib.lines.Line2D)]
    assert len(event_handles) == 1
    np.testing.assert_allclose(matplotlib.colors.to_rgba(event_handles[0].get_markerfacecolor()),
                               matplotlib.colors.to_rgba("red"))
    figure.canvas.draw()


def _assert_outline_has_points(patch, expected):
    vertices = patch.get_path().vertices
    for point in expected:
        assert np.any(np.all(np.isclose(vertices, point), axis=1)), f"Outline missing vertex {point}"


def test_loaded_region_outline_keeps_the_whole_grid_visible_for_a_tiny_fire():
    probability = np.full((5, 7), np.nan)
    probability[2, 3] = 0.2
    observed = np.zeros_like(probability)
    observed[2, 3] = 1
    prior = np.zeros_like(probability)
    prior[2, 2] = 1
    figure, axes = plot_comparison(
        probability, observed, burned_area=prior,
        region_valid=np.ones_like(probability, dtype=bool), colorbar=False,
    )
    ax = axes[0]
    assert len(ax.images) == 2 and len(ax.collections) == 1
    assert len(ax.patches) == 1
    assert isinstance(ax.patches[0], matplotlib.patches.PathPatch)
    assert not ax.patches[0].get_fill()
    _assert_outline_has_points(ax.patches[0], [(-0.5, -0.5), (6.5, -0.5), (6.5, 4.5), (-0.5, 4.5)])
    assert ax.get_xlim() == (-0.5, 6.5)
    assert ax.get_ylim() == (4.5, -0.5)
    np.testing.assert_array_equal(ax.collections[0].get_offsets(), [[3, 2]])
    figure.canvas.draw()


def test_region_outline_distinguishes_interior_holes_and_spatial_padding_without_cropping():
    region = np.ones((4, 5), dtype=bool)
    region[:, -1] = False
    region[1, 1] = False
    figure, axes = plot_comparison(
        np.full(region.shape, 0.25), np.zeros(region.shape), region_valid=region, colorbar=False,
    )
    patch = axes[0].patches[0]
    _assert_outline_has_points(patch, [(-0.5, -0.5), (3.5, -0.5), (3.5, 3.5), (-0.5, 3.5)])
    _assert_outline_has_points(patch, [(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5)])
    assert axes[0].get_xlim() == (-0.5, 4.5)
    assert axes[0].get_ylim() == (3.5, -0.5)
    figure.canvas.draw()


@pytest.mark.parametrize("origin", ["upper", "lower"])
@pytest.mark.parametrize("extent", [(10, 50, 100, 200), (50, 10, 200, 100)])
def test_region_outline_and_event_markers_use_matching_extent_and_origin(origin, extent):
    region = np.zeros((2, 4), dtype=bool)
    region[0, 1] = True
    observed = region.astype(np.uint8)
    figure, axes = plot_comparison(np.full(region.shape, 0.25), observed,
                                   region_valid=region, extent=extent, origin=origin, colorbar=False)
    left, right, bottom, top = extent
    x0 = left + (right - left) / 4
    x1 = left + 2 * (right - left) / 4
    if origin == "upper":
        y0, y1 = top, top - (top - bottom) / 2
    else:
        y0, y1 = bottom, bottom + (top - bottom) / 2
    _assert_outline_has_points(axes[0].patches[0], [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    np.testing.assert_allclose(axes[0].collections[0].get_offsets(), [[(x0 + x1) / 2, (y0 + y1) / 2]])
    assert axes[0].get_xlim() == (left, right)
    # With an explicit extent, Matplotlib preserves its (bottom, top) axis
    # limits; origin controls the row-to-y mapping within those limits.
    assert axes[0].get_ylim() == (bottom, top)
    figure.canvas.draw()


@pytest.mark.parametrize("shape", ["selected", "full"])
def test_region_mask_can_describe_the_selected_grid_or_full_batch_time_shape(shape):
    probability = np.full((2, 3, 1, 2, 4), 0.3)
    selected_region = np.zeros((2, 4), dtype=bool)
    selected_region[0, 2] = True
    if shape == "full":
        region = np.ones_like(probability, dtype=bool)
        region[1, 2, 0] = selected_region
    else:
        region = selected_region
    _, axes = plot_comparison(probability, np.zeros_like(probability),
                              region_valid=region, index=(1, 2), region_color="red", colorbar=False)
    assert len(axes[0].patches) == 1
    _assert_outline_has_points(axes[0].patches[0], [(1.5, -0.5), (2.5, -0.5), (2.5, 0.5), (1.5, 0.5)])
    np.testing.assert_allclose(axes[0].patches[0].get_edgecolor(), matplotlib.colors.to_rgba("red"))


def test_region_mask_requires_boolean_selected_or_matching_full_shapes():
    probability = np.full((2, 1, 2, 4), 0.3)
    observed = np.zeros_like(probability)
    with pytest.raises((TypeError, ValueError), match="region_valid"):
        plot_comparison(probability, observed, region_valid=np.ones((2, 4)), index=0)
    with pytest.raises(ValueError, match="region_valid"):
        plot_comparison(probability, observed, region_valid=np.ones((2, 3), dtype=bool), index=0)
    with pytest.raises(ValueError, match="region_valid"):
        plot_comparison(probability, observed, region_valid=np.ones((1, 1, 2, 4), dtype=bool), index=0)


def test_overlay_empty_events_and_unknown_cells_keep_raster_limits():
    _, axes = plot_comparison(np.full((2, 3), np.nan), np.zeros((2, 3)), mode="overlay", colorbar=False)
    assert axes[0].collections[0].get_offsets().shape == (0, 2)
    assert axes[0].get_xlim() == (-0.5, 2.5)
    assert axes[0].get_ylim() == (1.5, -0.5)


@pytest.mark.parametrize("origin,expected", [("upper", [[15, 175], [35, 125]]), ("lower", [[15, 125], [35, 175]])])
def test_overlay_extent_and_origin_align_event_markers(origin, expected):
    observed = np.array([[1, 0, 0, 0], [0, 0, 1, 0]])
    _, axes = plot_comparison(np.full((2, 4), 0.3), observed, mode="overlay",
                              extent=(10, 50, 100, 200), origin=origin, colorbar=False)
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), expected)
    assert axes[0].get_xlabel() == "x" and axes[0].get_ylabel() == "y"


def test_comparison_accepts_existing_axes_and_custom_titles_colors_and_markers():
    figure, axes = plt.subplots(1, 2)
    returned, result = plot_comparison(*comparison_values(), mode="side_by_side", axes=axes,
                                       titles=("Observed", "Forecast"), unknown_color="pink",
                                       event_color="red", colorbar=False)
    assert returned is figure
    assert list(result) == list(axes)
    assert [ax.get_title() for ax in result] == ["Observed", "Forecast"]
    np.testing.assert_allclose(result[0].images[0].cmap.get_bad(), matplotlib.colors.to_rgba("pink"))
    overlay_figure, overlay_ax = plt.subplots()
    _, overlay_axes = plot_comparison(*comparison_values(), mode="overlay", axes=overlay_ax,
                                      titles="Overlay", marker="s", marker_size=42, colorbar=False)
    assert overlay_axes[0].get_title() == "Overlay"
    np.testing.assert_array_equal(overlay_axes[0].collections[0].get_sizes(), [42])
    assert overlay_figure is overlay_axes[0].figure


@pytest.mark.parametrize("mode,expected", [("both", ["Events", "Probability", "Overlay"]),
                                          ("side_by_side", ["Events", "Probability"]),
                                          ("overlay", ["Overlay"])])
def test_all_modes_can_select_titles_from_one_semantic_triplet(mode, expected):
    _, axes = plot_comparison(*comparison_values(), mode=mode,
                              titles=("Events", "Probability", "Overlay"), colorbar=False)
    assert [ax.get_title() for ax in axes] == expected


def test_overlay_none_origin_uses_matplotlib_default_for_markers():
    with matplotlib.rc_context({"image.origin": "upper"}):
        _, axes = plot_comparison(np.array([[0.4], [0.6]]), np.array([[1], [0]]),
                                  mode="overlay", extent=(0, 2, 10, 14), origin=None, colorbar=False)
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[1, 13]])


def test_comparison_selects_leading_dimensions_with_each_mask():
    probability = np.full((2, 1, 2, 3), 0.2)
    observed = np.zeros_like(probability)
    observed[1, 0, 0, 2] = 1
    observed_valid = np.ones_like(observed, dtype=bool)
    observed_valid[1, 0, 1, 1] = False
    _, axes = plot_comparison(torch.from_numpy(probability), torch.from_numpy(observed),
                              observed_valid=torch.from_numpy(observed_valid), index=1, mode="both", colorbar=False)
    assert axes[0].images[0].get_array().shape == (2, 3)
    assert axes[0].images[0].get_array().mask[1, 1]
    np.testing.assert_array_equal(axes[2].collections[0].get_offsets(), [[2, 0]])


def test_comparison_requires_equal_full_shapes_even_if_slices_would_match():
    with pytest.raises(ValueError, match="must equal observed shape"):
        plot_comparison(np.ones((2, 1, 3, 4)), np.ones((1, 1, 3, 4)), index=0)
    with pytest.raises(ValueError, match="must equal observed shape"):
        plot_comparison(np.ones((1, 3, 4)), np.ones((3, 4)))


@pytest.mark.parametrize("probability", [-0.01, 1.01])
def test_comparison_rejects_known_probability_outside_unit_interval(probability):
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        plot_comparison(np.array([[probability]]), np.array([[0]]))


@pytest.mark.parametrize("observed", [-1, 0.5, 2])
def test_comparison_rejects_nonbinary_known_observation(observed):
    with pytest.raises(ValueError, match="binary"):
        plot_comparison(np.array([[0.5]]), np.array([[observed]]))


def test_comparison_validates_all_known_full_array_values_but_ignores_unknowns():
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        plot_comparison(np.array([[[0.5]], [[5.0]]]), np.zeros((2, 1, 1)), index=0)
    probability = np.ma.array([[0.4, 99.0]], mask=[[False, True]])
    observed = np.array([[1.0, 99.0]])
    _, axes = plot_comparison(probability, observed, observed_valid=np.array([[True, False]]), mode="both", colorbar=False)
    assert axes[2].images[0].get_array().mask[0, 1]


@pytest.mark.parametrize("option", ["vmin", "vmax", "norm"])
def test_comparison_prevents_probability_scale_override(option):
    with pytest.raises(ValueError, match="fixed probability range"):
        plot_comparison(np.zeros((1, 1)), np.zeros((1, 1)), **{option: None})


def test_comparison_rejects_invalid_modes_titles_and_axes():
    probability, observed = comparison_values()
    with pytest.raises(ValueError, match="mode"):
        plot_comparison(probability, observed, mode="threshold")
    with pytest.raises(ValueError, match="3 titles"):
        plot_comparison(probability, observed, titles="One title", mode="both")
    with pytest.raises(ValueError, match="3 titles"):
        plot_comparison(probability, observed, titles=["One"], mode="both")
    figure, ax = plt.subplots()
    with pytest.raises(ValueError, match="exactly 3"):
        plot_comparison(probability, observed, axes=ax, mode="both")
    with pytest.raises(ValueError, match="distinct"):
        plot_comparison(probability, observed, mode="side_by_side", axes=[ax, ax])
    _, other_ax = plt.subplots()
    with pytest.raises(ValueError, match="same figure"):
        plot_comparison(probability, observed, mode="side_by_side", axes=[ax, other_ax])


def test_default_comparison_is_one_overlay_with_three_independently_known_layers():
    probability = np.array([[0.2, np.nan, 0.6], [0.3, 0.4, 0.5]])
    observed = np.array([[np.nan, 1, 0], [1, 1, 0]])
    observed_valid = np.array([[True, True, True], [False, True, True]])
    burned = np.array([[1, 0, 1], [1, 1, np.nan]])
    burned_valid = np.array([[True, True, False], [True, True, True]])
    originals = [value.copy() for value in (probability, observed, observed_valid, burned, burned_valid)]

    figure, axes = plot_comparison(
        probability, observed, observed_valid=observed_valid,
        burned_area=burned, burned_area_valid=burned_valid, colorbar=False,
    )

    assert axes.shape == (1,) and len(figure.axes) == 1
    ax = axes[0]
    assert len(ax.images) == 2
    np.testing.assert_array_equal(np.ma.getmaskarray(ax.images[0].get_array()),
                                  [[False, True, False], [False, False, False]])
    # Missing next-hour labels must not hide available probabilities. Prior
    # burns must not conceal unburned cells or borrow prediction validity.
    assert ax.images[0].get_array()[0, 0] == probability[0, 0]
    np.testing.assert_array_equal(np.ma.getmaskarray(ax.images[1].get_array()),
                                  [[False, True, True], [False, False, True]])
    np.testing.assert_array_equal(ax.collections[0].get_offsets(), [[1, 0], [1, 1]])
    assert ax.images[1].get_alpha() == pytest.approx(0.65)
    np.testing.assert_allclose(ax.images[1].cmap(1.0), matplotlib.colors.to_rgba("#8b5a2b"))
    # Unknown prior cells are transparent rather than another unknown raster.
    assert ax.images[1].cmap.get_bad()[-1] == 0
    assert any("burned" in text.get_text().lower() for text in ax.get_legend().get_texts())
    for value, original in zip((probability, observed, observed_valid, burned, burned_valid), originals):
        np.testing.assert_array_equal(value, original)
    figure.canvas.draw()


@pytest.mark.parametrize("mode,count", [("both", 3), ("side_by_side", 2), ("overlay", 1)])
def test_previous_burns_are_shown_only_on_overlay_panels(mode, count):
    figure, axes = plot_comparison(
        np.full((2, 3), 0.25), np.zeros((2, 3)),
        burned_area=np.array([[1, 0, 0], [0, 1, 0]]), mode=mode, colorbar=False,
    )
    assert axes.shape == (count,)
    expected_images = [1, 1, 2] if mode == "both" else ([1, 1] if mode == "side_by_side" else [2])
    assert [len(ax.images) for ax in axes] == expected_images
    figure.canvas.draw()


@pytest.mark.parametrize("origin", ["upper", "lower"])
def test_prior_raster_uses_the_selected_batch_time_grid_and_shared_extent(origin):
    probability = np.full((2, 3, 1, 2, 4), 0.5)
    observed = np.zeros_like(probability)
    observed[1, 2, 0, 1, 3] = 1
    burned = np.zeros_like(probability)
    burned[1, 2, 0, 0, 2] = 1
    burned[0, 2, 0, 1, 1] = 1
    burned[1, 1, 0, 0, 0] = 1
    _, axes = plot_comparison(
        torch.from_numpy(probability), torch.from_numpy(observed),
        burned_area=torch.from_numpy(burned), index=(1, -1),
        extent=(10, 50, 100, 200), origin=origin,
        burned_color="red", burned_alpha=0.4, colorbar=False,
    )
    prior = axes[0].images[1]
    expected_mask = np.ones((2, 4), dtype=bool)
    expected_mask[0, 2] = False
    np.testing.assert_array_equal(np.ma.getmaskarray(prior.get_array()), expected_mask)
    assert tuple(prior.get_extent()) == (10, 50, 100, 200)
    assert prior.origin == origin
    assert prior.get_alpha() == pytest.approx(0.4)
    np.testing.assert_allclose(prior.cmap(1.0), matplotlib.colors.to_rgba("red"))
    expected_y = 125 if origin == "upper" else 175
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[45, expected_y]])


def test_prior_full_shape_validity_and_masked_values_are_preserved():
    probability = np.full((2, 1, 2, 3), 0.5)
    burned = np.ma.array(np.ones_like(probability), mask=False)
    burned.mask[1, 0, 0, 0] = True
    burned[1, 0, 0, 1] = np.nan
    valid = np.ones_like(probability, dtype=bool)
    valid[1, 0, 0, 2] = False
    _, axes = plot_comparison(probability, np.zeros_like(probability),
                              burned_area=burned, burned_area_valid=valid, index=1, colorbar=False)
    np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[1].get_array()),
                                  [[True, True, True], [False, False, False]])


def test_prior_values_are_checked_before_time_selection_and_unknowns_are_ignored():
    probability = np.full((2, 1, 2, 3), 0.5)
    prior = np.zeros_like(probability)
    prior[1, 0, 1, 1] = 0.5
    with pytest.raises(ValueError, match="binary|0 or 1"):
        plot_comparison(probability, np.zeros_like(probability), burned_area=prior, index=0)
    valid = np.ones_like(prior, dtype=bool)
    valid[1, 0, 1, 1] = False
    _, axes = plot_comparison(probability, np.zeros_like(probability),
                              burned_area=prior, burned_area_valid=valid, index=1, colorbar=False)
    assert np.ma.getmaskarray(axes[0].images[1].get_array()).all()


@pytest.mark.parametrize("prior", [-1, 0.5, 2])
def test_prior_known_values_must_be_binary(prior):
    with pytest.raises(ValueError, match="binary|0 or 1"):
        plot_comparison([[0.5]], [[0]], burned_area=[[prior]])


def test_prior_requires_matching_full_shapes_and_boolean_validity():
    probability = np.full((2, 1, 2, 3), 0.5)
    target = np.zeros_like(probability)
    with pytest.raises(ValueError, match="shape"):
        plot_comparison(probability, target, burned_area=np.zeros((2, 3)), index=0)
    with pytest.raises(ValueError, match="shape"):
        plot_comparison(probability, target, burned_area=target,
                        burned_area_valid=np.ones((2, 3), dtype=bool), index=0)
    with pytest.raises(TypeError, match="booleans"):
        plot_comparison(probability, target, burned_area=target, burned_area_valid=np.ones_like(target), index=0)
    with pytest.raises((TypeError, ValueError), match="burned_area"):
        plot_comparison(probability, target, burned_area_valid=np.ones_like(target, dtype=bool), index=0)
    with pytest.raises(TypeError, match="real numeric"):
        plot_comparison([[0.5]], [[0]], burned_area=[["burned"]])


@pytest.mark.parametrize("alpha", [-0.1, 1.1, np.nan, np.inf, "0.5", True, None])
def test_prior_alpha_must_be_a_finite_real_number_between_zero_and_one(alpha):
    with pytest.raises((TypeError, ValueError), match="burned_alpha"):
        plot_comparison([[0.5]], [[0]], burned_area=[[1]], burned_alpha=alpha)


@pytest.mark.parametrize("alpha", [0, 1, np.float64(0.25)])
def test_prior_alpha_accepts_the_closed_unit_interval(alpha):
    _, axes = plot_comparison([[0.5]], [[0]], burned_area=[[1]], burned_alpha=alpha, colorbar=False)
    assert axes[0].images[1].get_alpha() == pytest.approx(alpha)

