"""Live camera input (src/wfglink/io/camera.py): discovery, choice, permission and capture, with fakes."""
import sys
import threading
import types

import numpy as np
import pytest

from wfglink.io import camera as C
from wfglink.io.sources import SourceError

BUILTIN = {"name": "MacBook Pro Camera", "unique_id": "47B4B64B-7067-4B9C", "device_type": "AVCaptureDeviceTypeBuiltInWideAngleCamera",
           "transport": "bltn", "index": 1}
WEBCAM = {"name": "C920 HD Pro Webcam", "unique_id": "0x11400000046d082d", "device_type": "AVCaptureDeviceTypeExternal",
          "transport": "usb ", "index": 0}
IPHONE = {"name": "Seo's iPhone Camera", "unique_id": "AAAA-1111", "device_type": "AVCaptureDeviceTypeContinuityCamera",
          "transport": "", "is_continuity": True}
IPHONE_NAMED_ONLY = {"name": "iPhone 16 Camera", "unique_id": "BBBB", "device_type": "AVCaptureDeviceTypeExternal",
                     "transport": "usb "}
DESKVIEW = {"name": "Seo's iPhone Desk View Camera", "unique_id": "CCCC", "device_type": "AVCaptureDeviceTypeDeskViewCamera"}
VIRTUAL = {"name": "OBS Virtual Camera", "unique_id": "7626645E", "device_type": "AVCaptureDeviceTypeExternal",
           "transport": "virt"}


def test_kinds_and_what_is_never_used():
    got = {d["name"]: d for d in C.list_cameras([BUILTIN, WEBCAM, IPHONE, IPHONE_NAMED_ONLY, DESKVIEW, VIRTUAL])}
    assert got["MacBook Pro Camera"]["kind"] == "builtin" and got["MacBook Pro Camera"]["usable"]
    assert got["C920 HD Pro Webcam"]["kind"] == "usb" and got["C920 HD Pro Webcam"]["usable"]
    for name in ("Seo's iPhone Camera", "iPhone 16 Camera"):
        assert got[name]["kind"] == "continuity" and not got[name]["usable"] and "never" in got[name]["why"]
    assert got["Seo's iPhone Desk View Camera"]["kind"] in ("continuity", "deskview")
    assert not got["Seo's iPhone Desk View Camera"]["usable"]
    desk = C.classify({"name": "Desk View Camera", "unique_id": "D", "device_type": "AVCaptureDeviceTypeDeskViewCamera"})
    assert desk["kind"] == "deskview" and not desk["usable"]
    assert got["OBS Virtual Camera"]["kind"] == "other"
    # A FaceTime camera without a transport code is still the built-in one; a closed lid suspends it.
    assert C.classify({"name": "FaceTime HD Camera", "unique_id": "F"})["kind"] == "builtin"
    lid = C.classify(dict(BUILTIN, suspended=True))
    assert not lid["usable"] and "lid" in lid["why"]
    # USB webcams first, then the built-in camera, then the rest.
    order = [d["kind"] for d in C.list_cameras([VIRTUAL, BUILTIN, IPHONE, WEBCAM])]
    assert order == ["usb", "builtin", "other", "continuity"]


def test_pick_by_auto_and_by_name():
    devs = [BUILTIN, WEBCAM, IPHONE, DESKVIEW, VIRTUAL]
    assert C.pick_camera({"camera": {"name": "auto"}}, devs)["name"] == "C920 HD Pro Webcam"
    assert C.pick_camera({}, [BUILTIN, IPHONE, VIRTUAL])["name"] == "MacBook Pro Camera"      # auto is the default
    assert C.pick_camera({"camera": {"name": "auto"}}, [IPHONE, DESKVIEW, VIRTUAL]) is None    # never a phone or virtual
    assert C.pick_camera({"camera": {"name": "macbook"}}, devs)["name"] == "MacBook Pro Camera"
    assert C.pick_camera({"camera": {"name": "OBS"}}, devs)["name"] == "OBS Virtual Camera"
    assert C.pick_camera({"camera": {"name": "iphone"}}, devs) is None
    why = C.explain_pick({"camera": {"name": "iphone"}}, devs)
    assert "Continuity" in why
    assert "no camera name contains" in C.explain_pick({"camera": {"name": "logitech brio"}}, devs)
    assert "no camera found" in C.explain_pick({}, [])


def test_opencv_order_follows_sorted_unique_ids():
    order = C.opencv_order(["47B4B64B-7067", "0x11400000046d082d", "AAAA-1111"])
    assert order == {"0x11400000046d082d": 0, "47B4B64B-7067": 1, "AAAA-1111": 2}


def test_permission_elsewhere_is_unsupported():
    if sys.platform == "darwin":
        pytest.skip("macOS asks for real")
    assert C.permission_status() == "unsupported"
    assert C.request_permission(0.1) == "unsupported"


def _fake_avfoundation(monkeypatch, start: int, answer: bool | None):
    """A fake pyobjc AVFoundation and Foundation: the status, and the dialog's answer."""
    state = {"status": start, "asked": 0}

    class Device:
        @staticmethod
        def authorizationStatusForMediaType_(media):
            return state["status"]

        @staticmethod
        def requestAccessForMediaType_completionHandler_(media, handler):
            state["asked"] += 1
            if answer is not None:
                state["status"] = 3 if answer else 2
                handler(answer)

    avf = types.SimpleNamespace(AVCaptureDevice=Device, AVMediaTypeVideo="vide")

    class RunLoop:
        @staticmethod
        def currentRunLoop():
            return RunLoop()

        def runUntilDate_(self, date):
            pass

    foundation = types.ModuleType("Foundation")
    foundation.NSRunLoop = RunLoop
    foundation.NSDate = types.SimpleNamespace(dateWithTimeIntervalSinceNow_=lambda s: s)
    monkeypatch.setitem(sys.modules, "Foundation", foundation)
    monkeypatch.setattr(C.sys, "platform", "darwin")
    monkeypatch.setattr(C, "_avf", lambda: avf)
    return state


def test_permission_request_on_the_main_thread(monkeypatch):
    state = _fake_avfoundation(monkeypatch, 0, True)
    assert C.permission_status() == "not_determined"
    assert C.request_permission(1.0) == "authorized" and state["asked"] == 1
    assert C.request_permission(1.0) == "authorized" and state["asked"] == 1      # asked once only
    state = _fake_avfoundation(monkeypatch, 0, False)
    assert C.request_permission(1.0) == "denied"
    state = _fake_avfoundation(monkeypatch, 1, None)
    assert C.request_permission(1.0) == "restricted" and state["asked"] == 0


def test_permission_is_never_asked_from_a_capture_thread(monkeypatch):
    state = _fake_avfoundation(monkeypatch, 0, True)
    out = {}
    th = threading.Thread(target=lambda: out.setdefault("s", C.request_permission(1.0)))
    th.start()
    th.join()
    assert out["s"] == "not_determined" and state["asked"] == 0


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class FakeBackend:
    """A capture backend: frames of the given size; fails reads while `broken` is set."""

    script = {"open_fail": set(), "broken": False, "size": (1280, 720), "opened": []}

    def __init__(self, device, width, height, fps, devices):
        self.device = device
        self.n = 0
        self.options = {"fake": "1"}

    def open(self, timeout_s):
        self.script["opened"].append(type(self).name)
        if type(self).name in self.script["open_fail"]:
            raise SourceError("no such device")

    def read(self):
        if self.script["broken"]:
            raise SourceError("unplugged")
        self.n += 1
        w, h = self.script["size"]
        return np.full((h, w, 3), self.n % 255, np.uint8), 10.0 + self.n / 30.0

    def close(self):
        pass


class FakePyAV(FakeBackend):
    name = "pyav"


class FakeOpenCV(FakeBackend):
    name = "opencv"


@pytest.fixture
def fake_backends(monkeypatch):
    FakeBackend.script = {"open_fail": set(), "broken": False, "size": (1280, 720), "opened": []}
    C.CameraSource._winners.clear()
    monkeypatch.setattr(C, "permission_status", lambda: "authorized")
    return {"pyav": FakePyAV, "opencv": FakeOpenCV}


def test_camera_source_opens_reads_and_reopens_after_a_failure(fake_backends, monkeypatch):
    monkeypatch.setattr(C.time, "sleep", lambda s: None)
    clock = FakeClock()
    cfg = {"camera": {"name": "auto", "backoff_min_s": 0.5, "backoff_max_s": 2.0}}
    src = C.CameraSource(cfg, clock=clock, devices=lambda: C.list_cameras([BUILTIN, WEBCAM]), backends=fake_backends)
    src.open()
    assert src.state == "ok" and src.name == "C920 HD Pro Webcam" and src.backend == "pyav"
    ts = []
    for _ in range(5):
        clock.now += 1 / 30
        f = src.read()
        ts.append(f.t)
        assert f.meta["camera"] == "C920 HD Pro Webcam" and f.image.shape == (720, 1280, 3)
    assert np.all(np.diff(ts) > 0)
    FakeBackend.script["broken"] = True
    clock.now += 0.03
    assert src.read() is None and src.state == "reconnecting"
    FakeBackend.script["broken"] = False
    clock.now += 0.1
    assert src.read() is None                                # still backing off
    clock.now += 0.6
    f = src.read()
    assert f is not None and src.state == "ok" and src.reopens == 1 and f.t > ts[-1]


def test_backend_fallback_and_scaling(fake_backends):
    FakeBackend.script["open_fail"] = {"pyav"}
    FakeBackend.script["size"] = (1920, 1080)
    src = C.CameraSource({"camera": {"name": "macbook", "width": 1280}}, devices=lambda: C.list_cameras([BUILTIN, WEBCAM]),
                         backends=fake_backends)
    src.open()
    assert src.backend == "opencv" and src.name == "MacBook Pro Camera"
    assert src.read().image.shape == (720, 1280, 3)          # scaled down to camera.width
    assert src.info["native_size"] == [1920, 1080]
    src.close()
    # The backend that worked is tried first next time.
    FakeBackend.script["opened"].clear()
    src2 = C.CameraSource({"camera": {"name": "macbook"}}, devices=lambda: C.list_cameras([BUILTIN]), backends=fake_backends)
    src2.open()
    assert FakeBackend.script["opened"][0] == "opencv"


def test_open_fails_clearly_without_camera_or_permission(fake_backends, monkeypatch):
    src = C.CameraSource({"camera": {"name": "auto"}}, devices=lambda: C.list_cameras([IPHONE, DESKVIEW]),
                         backends=fake_backends)
    with pytest.raises(SourceError, match="no built-in or USB camera"):
        src.open()
    assert src.state == "no_camera"
    monkeypatch.setattr(C, "permission_status", lambda: "denied")
    src = C.CameraSource({}, devices=lambda: C.list_cameras([WEBCAM]), backends=fake_backends)
    with pytest.raises(SourceError, match="Privacy and Security"):
        src.open()
    assert src.state == "denied"


def test_fake_camera_plays_a_file_and_a_generated_scene(tmp_path):
    from wfglink.synth.degrade import VideoWriter

    path = tmp_path / "clip.mp4"
    with VideoWriter(path, (320, 180), 30, crf=23, threaded=False) as wr:
        for i in range(10):
            wr.write(np.full((180, 320, 3), 20 * i, np.uint8), i / 30)
    src = C.FakeCameraSource(path, realtime=False, loop=True)
    src.open()
    frames = [src.read() for _ in range(15)]                 # loops past the end
    assert all(f is not None for f in frames) and frames[0].meta["camera"] == "fake: clip.mp4"
    assert not frames[0].meta["synthetic"] and np.all(np.diff([f.t for f in frames]) > 0)
    src.close()
    gen = C.FakeCameraSource(scene="one_at_2m", realtime=False, size=(320, 180), fps=30)
    gen.open()
    f1, f2 = gen.read(), gen.read()
    assert f1.image.shape == (180, 320, 3) and f1.meta["synthetic"] and f2.t > f1.t
    gen.close()


def test_cameras_command_lists_and_explains(monkeypatch, capsys):
    from wfglink import cli

    devs = C.list_cameras([BUILTIN, WEBCAM, IPHONE])
    monkeypatch.setattr(C, "list_cameras", lambda raw=None: devs)
    monkeypatch.setattr(C, "permission_status", lambda: "authorized")
    assert cli.main(["cameras"]) == 0
    out = capsys.readouterr().out
    assert "* C920 HD Pro Webcam  (usb" in out and "Continuity Camera" in out and "permission: authorized" in out
    monkeypatch.setattr(C, "list_cameras", lambda raw=None: [])
    assert cli.main(["cameras"]) == 1
    assert "no camera found" in capsys.readouterr().out


class _EagainContainer:
    """FFmpeg's avfoundation input as PyAV shows it: EAGAIN (BlockingIOError) until a frame is ready."""

    def __init__(self, eagain: int):
        self.eagain = eagain

    def demux(self, stream):
        if self.eagain > 0:
            self.eagain -= 1
            raise BlockingIOError(11, "Resource temporarily unavailable")
        frame = types.SimpleNamespace(time=12.5, to_ndarray=lambda format: np.zeros((4, 6, 3), np.uint8))
        yield types.SimpleNamespace(size=100, decode=lambda: [frame])


def test_pyav_backend_waits_through_eagain():
    cam = C._PyAVCamera(WEBCAM, 1280, 720, 30, [WEBCAM])
    cam._container, cam._stream = _EagainContainer(5), object()
    img, t = cam.read(wait_s=1.0)
    assert img.shape == (4, 6, 3) and t == 12.5
    cam._container = _EagainContainer(10 ** 9)
    assert cam.read(wait_s=0.02) is None                   # nothing yet: the caller decides when it has stalled


def test_pyav_backend_reads_a_stream_packet_by_packet(tmp_path):
    import av

    from wfglink.synth.degrade import VideoWriter

    path = tmp_path / "cam.mp4"
    with VideoWriter(path, (64, 48), 30, crf=23, threaded=False) as wr:
        for i in range(12):
            wr.write(np.full((48, 64, 3), 10 * i, np.uint8), i / 30)
    cam = C._PyAVCamera(WEBCAM, 64, 48, 30, [WEBCAM])
    cam._container = av.open(str(path))
    cam._stream = cam._container.streams.video[0]
    times = [cam.read()[1] for _ in range(12)]
    assert times == pytest.approx([i / 30 for i in range(12)], abs=1e-3)
    with pytest.raises(SourceError, match="ended"):
        cam.read()
    cam.close()
