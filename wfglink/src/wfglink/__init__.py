"""wfglink: measure glowing wildfire embers and an ember-derived wind estimate from ordinary video."""

import os
import sys
from pathlib import Path

__version__ = "0.1.0"

# wfglink/ project root (contains README.md, configs/, assets/, data/, results/).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if sys.platform == "darwin":
    # OpenCV's AVFoundation backend can only ask for camera permission from the main
    # thread; wfglink asks itself (wfglink.io.macos.request_camera_access) before any
    # capture thread starts, so OpenCV must not try. Set before cv2 is first imported.
    os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")
