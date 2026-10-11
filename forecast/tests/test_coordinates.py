"""Independent geometry checks for the public Earth-coordinate contract."""

import numpy as np
import pytest

from wildfire.coordinates import geographic_coordinates
from wildfire.coordinates import geographic_coordinates_for_points
from wildfire.coordinates import validate_metric_crs


def test_coordinates_use_rotated_affine_pixel_centers_and_latitude_first():
    transform = (0.1, 0.02, 127.0, 0.03, -0.1, 38.0)
    result = geographic_coordinates((2, 3), affine_transform=transform, epsg=4326)
    assert result.shape == (2, 3, 2) and result.dtype == np.float64
    # First and last pixel centers include both affine cross terms.
    np.testing.assert_allclose(result[0, 0], (37.965, 127.06), rtol=0, atol=1e-12)
    np.testing.assert_allclose(result[1, 2], (37.925, 127.28), rtol=0, atol=1e-12)


def test_projected_korean_grid_returns_earth_locations_instead_of_metric_xy():
    # EPSG:5179 places its latitude/longitude origin (38,127.5) at (1e6,2e6).
    transform = (375, 0, 999812.5, 0, -375, 2000187.5)
    result = geographic_coordinates((1, 1), affine_transform=transform, epsg=5179)
    np.testing.assert_allclose(result[0, 0], (38.0, 127.5), rtol=0, atol=1e-10)
    points = geographic_coordinates_for_points([[1000000, 2000000]], epsg=5179)
    np.testing.assert_array_equal(result[0], points)


def test_batch_grids_and_crs_align_before_time_and_channel_with_padding():
    shape = (2, 3, 1, 2, 3)
    transforms = [[0.1, 0, 127.0, 0, -0.1, 38.0],
                  [1000, 0, -500, 0, -1000, 500]]
    pixels = np.ones((2, 1, 2, 3), dtype=bool)
    pixels[0, 0, 1, :] = False
    pixels[1, 0, :, 2] = False
    times = np.array([[True, True, False], [True, False, True]])
    result = geographic_coordinates(shape, affine_transform=transforms,
                                    epsg=np.array([4326, 3857]),
                                    pixel_valid=pixels, time_valid=times)
    assert result.shape == shape + (2,)
    np.testing.assert_allclose(result[0, 0, 0, 0, 0], (37.95, 127.05), atol=1e-12)
    np.testing.assert_array_equal(result[0, 0], result[0, 1])
    assert np.isnan(result[0, 2]).all()
    assert np.isnan(result[0, :, 0, 1]).all()
    assert np.isnan(result[1, 1]).all()
    assert np.isnan(result[1, :, 0, :, 2]).all()
    np.testing.assert_array_equal(result[1, 0], result[1, 2])
    np.testing.assert_allclose(result[1, 0, 0, 0, 0], (0, 0), atol=1e-12)
    # An independent spherical-Mercator inverse checks a second projected cell.
    radians_to_degrees = 180 / np.pi
    expected = (np.arctan(np.sinh(-1000 / 6378137)) * radians_to_degrees,
                1000 / 6378137 * radians_to_degrees)
    np.testing.assert_allclose(result[1, 0, 0, 1, 1], expected, atol=1e-12)


def test_common_grid_broadcasts_and_padded_pixels_outside_earth_are_not_transformed():
    # Second row would have latitude 90.15; it is spatial padding and has no site.
    pixels = np.array([[[True, True], [False, False]]])
    result = geographic_coordinates((2, 1, 2, 2),
                                    affine_transform=(0.1, 0, 127, 0, 0.1, 90),
                                    epsg=4326, pixel_valid=pixels,
                                    time_valid=np.array([False, False]))
    assert np.isnan(result).all()
    result = geographic_coordinates((2, 2), affine_transform=(0.1, 0, 127, 0, 0.1, 89.9),
                                    epsg=4326, pixel_valid=pixels, time_valid=np.array([True]))
    np.testing.assert_allclose(result[0, 0], (89.95, 127.05), atol=1e-12)
    assert np.isnan(result[1]).all()


def test_point_conversion_retains_shape_and_supports_empty_receiver_lists():
    points = np.array([[[127.0, 38.0], [128.0, 37.0]]])
    result = geographic_coordinates_for_points(points, epsg=4326)
    np.testing.assert_array_equal(result, points[..., ::-1])
    assert geographic_coordinates_for_points(np.empty((0, 2)), epsg=4326).shape == (0, 2)


def test_tensor_like_metadata_is_detached_to_cpu_without_tensor_import():
    class TensorLike:
        def __init__(self, value):
            self.value = np.asarray(value)
            self.steps = []

        def detach(self):
            self.steps.append("detach")
            return self

        def cpu(self):
            self.steps.append("cpu")
            return self

        def numpy(self):
            self.steps.append("numpy")
            return self.value

    transform = TensorLike([0.1, 0, 127, 0, -0.1, 38])
    epsg = TensorLike(4326)
    result = geographic_coordinates((1, 1), affine_transform=transform, epsg=epsg)
    np.testing.assert_allclose(result[0, 0], (37.95, 127.05))
    assert transform.steps == epsg.steps == ["detach", "cpu", "numpy"]


@pytest.mark.parametrize("epsg", [None, True, 4326.0, "4326", 0, -1, 99999999])
def test_invalid_epsg_is_rejected_even_when_all_snapshots_are_padding(epsg):
    with pytest.raises(ValueError, match="epsg|EPSG"):
        geographic_coordinates((1, 1), affine_transform=(1, 0, 0, 0, 1, 0),
                               epsg=epsg, time_valid=False)


@pytest.mark.parametrize("transform", [None, [1, 2], [1, 0, 0, 0, 0, 0],
                                        [1, 0, float("nan"), 0, 1, 0],
                                        [1 + 1j, 0, 0, 0, 1, 0]])
def test_invalid_affine_transform_is_rejected(transform):
    with pytest.raises(ValueError, match="affine_transform"):
        geographic_coordinates((1, 1), affine_transform=transform, epsg=4326)


@pytest.mark.parametrize("shape", [(0, 1), (True, 1), (1.0, 1), (1,), None])
def test_invalid_prediction_shape_is_rejected(shape):
    with pytest.raises(ValueError, match="shape"):
        geographic_coordinates(shape, affine_transform=(1, 0, 0, 0, 1, 0), epsg=4326)


@pytest.mark.parametrize("options", [
    {"affine_transform": np.ones((3, 6))},
    {"epsg": np.array([4326, 4326, 4326])},
    {"pixel_valid": np.ones((2, 2), bool)},
    {"pixel_valid": np.ones((1, 1), int)},
    {"time_valid": np.array([True, False, True])},
    {"time_valid": 1},
])
def test_metadata_shape_mismatches_and_nonboolean_padding_masks_are_rejected(options):
    arguments = dict(affine_transform=(0.1, 0, 127, 0, -0.1, 38), epsg=4326)
    arguments.update(options)
    with pytest.raises(ValueError):
        geographic_coordinates((2, 1, 1, 1), **arguments)


@pytest.mark.parametrize("epsg", [4326, 2263, None, True, 5179.0, [5179]])
def test_heat_metric_crs_validation_rejects_geographic_feet_and_nonscalar_metadata(epsg):
    with pytest.raises(ValueError, match="epsg|projected CRS"):
        validate_metric_crs(epsg)


def test_metric_crs_validation_preserves_supported_integer_code():
    assert validate_metric_crs(np.int64(5179)) == 5179
    assert validate_metric_crs(32652) == 32652


@pytest.mark.parametrize("points", [[[float("nan"), 38]], [[127, 95]], [[127]], [[1j, 38]]])
def test_invalid_point_locations_are_rejected(points):
    with pytest.raises(ValueError, match="coordinates"):
        geographic_coordinates_for_points(points, epsg=4326)
