"""Entry point inside WFGLink.app (py2app alias mode).

The bundle exists only to carry the camera Info.plist keys that newer macOS versions
require for Continuity Camera (NSCameraUseContinuityCameraDeviceType) and a stable
camera-permission identity. Arguments after `open -a WFGLink.app --args` are passed to the
normal wfglink command line; with no arguments the booth starts.
"""
import sys

from wfglink.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["booth"]))
