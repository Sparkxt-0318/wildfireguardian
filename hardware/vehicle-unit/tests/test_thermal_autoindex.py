"""``thermal`` ``index: auto``: find the InfiRay P2 Pro capture node by USB id in a FAKE sysfs tree (no camera)."""
import os

import numpy as np
import pytest

from wfgvu import protocol
from wfgvu.drivers import base, thermal_tc001 as th


def make_sysfs(root, nodes):
    """nodes: list of (n, usb_id or None, index, name). Builds class/video4linux/videoN/device -> USB interface."""
    for n, usb, idx, name in nodes:
        vdir = root / "class" / "video4linux" / ("video%d" % n)
        vdir.mkdir(parents=True)
        (vdir / "index").write_text("%d\n" % idx)
        (vdir / "name").write_text(name + "\n")
        if usb is None:
            dev = root / "devices" / "platform" / ("codec%d" % n)
            dev.mkdir(parents=True, exist_ok=True)
        else:
            port = "1-1.%d" % (n // 2 + 1) if usb != th.DEFAULT_USB_ID else "1-1.4"
            udev = root / "devices" / "platform" / "usb1" / "1-1" / port
            udev.mkdir(parents=True, exist_ok=True)
            v, p = usb.split(":")
            (udev / "idVendor").write_text(v + "\n")
            (udev / "idProduct").write_text(p + "\n")
            dev = udev / (port + ":1.0")
            dev.mkdir(exist_ok=True)
        os.symlink(os.path.relpath(dev, vdir), vdir / "device")


def test_auto_picks_the_capture_node_of_the_p2_pro(tmp_path):
    make_sysfs(tmp_path, [(0, None, 0, "bcm2835-codec-decode"), (1, None, 1, "bcm2835-codec-encode"),
                          (2, "046d:0825", 0, "UVC webcam"), (3, "046d:0825", 1, "UVC webcam"),
                          (4, "0bda:5830", 0, "USB Camera: USB Camera"), (5, "0bda:5830", 1, "USB Camera")])
    assert th.find_capture_node("0bda:5830", str(tmp_path)) == 4
    assert th.resolve_index({"index": "auto", "usb_id": "0BDA:5830"}, str(tmp_path)) == 4
    assert th.resolve_index({}, str(tmp_path)) == 4                     # missing index = auto, default usb id


def test_metadata_node_alone_is_not_used(tmp_path):
    make_sysfs(tmp_path, [(6, "0bda:5830", 1, "USB Camera")])
    with pytest.raises(base.DeviceUnavailable) as e:
        th.find_capture_node("0bda:5830", str(tmp_path))
    assert "video6" in str(e.value) and "index 1" in str(e.value)


def test_not_found_lists_what_was_seen(tmp_path):
    make_sysfs(tmp_path, [(0, None, 0, "bcm2835-codec"), (2, "046d:0825", 0, "UVC webcam")])
    with pytest.raises(base.DeviceUnavailable) as e:
        th.find_capture_node("0bda:5830", str(tmp_path))
    msg = str(e.value)
    assert "0bda:5830" in msg and "InfiRay P2 Pro" in msg and "video0" in msg and "046d:0825" in msg


def test_no_v4l2_tree(tmp_path):
    with pytest.raises(base.DeviceUnavailable, match="video4linux"):
        th.find_capture_node("0bda:5830", str(tmp_path))


def test_integer_index_still_works(tmp_path):
    assert th.resolve_index({"index": 3}, str(tmp_path)) == 3
    assert th.resolve_index({"index": "7"}, str(tmp_path)) == 7
    with pytest.raises(ValueError):
        th.resolve_index({"index": "camera"}, str(tmp_path))
    with pytest.raises(ValueError):
        th.resolve_index({"index": True}, str(tmp_path))


def test_two_cameras_lowest_capture_node_wins(tmp_path):
    make_sysfs(tmp_path, [(9, "0bda:5830", 0, "USB Camera")])
    # second camera on another port
    vdir = tmp_path / "class" / "video4linux" / "video7"
    vdir.mkdir(parents=True)
    (vdir / "index").write_text("0\n")
    udev = tmp_path / "devices" / "platform" / "usb1" / "1-1" / "1-1.2"
    udev.mkdir(parents=True)
    (udev / "idVendor").write_text("0bda\n")
    (udev / "idProduct").write_text("5830\n")
    (udev / "1-1.2:1.0").mkdir()
    os.symlink(os.path.relpath(udev / "1-1.2:1.0", vdir), vdir / "device")
    assert th.find_capture_node("0bda:5830", str(tmp_path)) == 7


def test_driver_auto_without_camera_reports_no_device(tmp_path):
    msgs = []
    ctx = protocol.Context(unit_id="VU-01", session_id="VU-01-TEST", sim=False)
    d = th.ThermalTC001Driver("thermal", {"index": "auto", "retry_s": 0.05}, msgs.append, ctx=ctx,
                              sysfs_root=str(tmp_path))
    st = None
    try:
        d.open()
    except Exception as exc:                                  # noqa: BLE001
        st = str(exc)
    assert st is not None and ("cv2" in st or "video4linux" in st)


def test_camera_name_in_errors():
    with pytest.raises(ValueError, match="InfiRay P2 Pro"):
        th.split_frame(np.zeros(10, np.uint8))
