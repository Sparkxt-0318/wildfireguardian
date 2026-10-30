"""Opt-in deterministic flame-front radiation research law."""
from .isochrone import AffineGrid, FrontSegment, UnsupportedGeometry, front_segments
from .law_v2 import flux_at_points, flux_enclosure, dose, bal_band
from .provenance import provenance, LAW_VERSION

__all__=["AffineGrid","FrontSegment","UnsupportedGeometry","front_segments","flux_at_points","flux_enclosure","dose","bal_band","provenance","LAW_VERSION"]
