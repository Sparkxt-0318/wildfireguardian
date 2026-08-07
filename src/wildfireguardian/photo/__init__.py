"""Reading a reported coordinate out of a photograph, and nothing else.

Round-3 PHASE 22 STEP 2.

⚠ THIS PACKAGE IS THE ENTIRE PRIVACY BOUNDARY. One module, one job. If a second
thing is ever read out of an uploaded photograph, it has to be added here, in
front of whoever is reviewing the change. That is the point of the package
existing at all rather than the function living in ``service/``.
"""

from .exif_gps import (
    GPS_ONLY_TAGS, MAX_BYTES, PRIVACY_KO, GpsReading, OUTCOMES, read_gps,
    sniff_container,
)

__all__ = [
    "GPS_ONLY_TAGS", "MAX_BYTES", "OUTCOMES", "PRIVACY_KO", "GpsReading",
    "read_gps", "sniff_container",
]
