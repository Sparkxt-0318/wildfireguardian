"""py2app build description for WFGLink.app. Use scripts/make_app.sh, not this file directly.

Alias mode (-A) links the app to the source tree and the project virtual environment, so
it builds in seconds and never needs rebuilding after code changes. Rebuilding changes the
code signature, so macOS asks for camera permission again (the booth runbook says so).
"""
from pathlib import Path

from setuptools import setup

HERE = Path(__file__).resolve().parent

PLIST = {
    "CFBundleName": "WFGLink",
    "CFBundleDisplayName": "WFGLink",
    "CFBundleIdentifier": "org.wildfireguardian.wfglink",
    "CFBundleShortVersionString": "0.1.0",
    "LSMinimumSystemVersion": "14.0",
    "NSHighResolutionCapable": True,
    "NSCameraUsageDescription": "WFGLink measures glowing embers in the live camera picture.",
    "NSCameraUseContinuityCameraDeviceType": True,
    "NSCameraReactionEffectGesturesEnabledDefault": False,
}

setup(
    name="WFGLink",
    app=[str(HERE / "app_main.py")],
    options={"py2app": {"plist": PLIST, "argv_emulation": False, "semi_standalone": False}},
)
