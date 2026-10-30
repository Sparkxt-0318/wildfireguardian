"""A planar elevation field fixes the sign and magnitude of a hand feature."""
import numpy as np

from wildfire.baselines import hand_features


def test_logistic_directional_slope_is_uphill_in_the_spread_direction():
    initial = np.zeros((3, 5), bool)
    initial[:, 2] = True
    # Elevation rises by one metre per metre eastward. Positive is uphill.
    gx, gy = np.ones(initial.shape), np.zeros(initial.shape)
    zeros = np.zeros(initial.shape)
    features = hand_features(initial, 1, zeros, zeros, zeros, None, [],
                             elevation_gradient=(gx, gy)).reshape(3, 5, -1)
    assert features[1, 3, 5] == 1.0
    assert features[1, 1, 5] == -1.0


def test_directional_slope_keeps_missing_elevation_unknown():
    initial = np.array([[True, False, False]])
    gradient = np.array([[0., np.nan, 0.]])
    zeros = np.zeros(initial.shape)
    features = hand_features(initial, 1, zeros, zeros, zeros, None, [],
                             elevation_gradient=(gradient, zeros))
    assert np.isnan(features[1, 5])
