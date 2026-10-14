"""Booth corner codes, rectification of a filmed screen and booth-prep round trip."""
import av
import cv2
import numpy as np
import pytest

from wfglink.io.synthetic_live import SyntheticLiveSource
from wfglink.screen.booth_prep import load_sidecar, prepare
from wfglink.screen.codes import Layout, draw_codes, gray_decode, gray_encode, read_frame_code
from wfglink.screen.rectify import ScreenRectifier


def test_gray_code_round_trip_and_single_bit_steps():
    for i in range(0, 65535, 7):
        assert gray_decode(gray_encode(i)) == i
        assert bin(gray_encode(i) ^ gray_encode(i + 1)).count("1") == 1


@pytest.mark.parametrize("w,h", [(1920, 1080), (1280, 720)])
def test_clean_blended_and_torn_frames(w, h):
    L = Layout.for_frame(w, h)
    base = np.full((h, w, 3), 30, np.uint8)
    a = draw_codes(base.copy(), 41, L)
    b = draw_codes(base.copy(), 42, L)
    fc = read_frame_code(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), L)
    assert fc.clean and fc.index == 41
    mix = cv2.addWeighted(a, 0.35, b, 0.65, 0)
    fc = read_frame_code(cv2.cvtColor(mix, cv2.COLOR_BGR2GRAY), L)
    assert fc.blended and not fc.clean
    assert all(c.blend == pytest.approx(0.65, abs=0.08) for c in fc.corners)
    torn = a.copy()
    torn[h // 2:] = b[h // 2:]
    fc = read_frame_code(cv2.cvtColor(torn, cv2.COLOR_BGR2GRAY), L)
    assert fc.torn and not fc.clean


def test_rectify_filmed_screen_recovers_code_and_positions():
    L = Layout.for_frame(1920, 1080)
    src = np.full((1080, 1920, 3), 25, np.uint8)
    pts = [(600, 400), (1000, 700), (1500, 300)]
    for x, y in pts:
        cv2.circle(src, (x, y), 4, (60, 160, 255), -1)
    draw_codes(src, 777, L)
    quad = np.float32([[380, 210], [1560, 250], [1530, 900], [400, 870]])
    Hs = cv2.getPerspectiveTransform(np.float32([[0, 0], [1919, 0], [1919, 1079], [0, 1079]]), quad)
    cam = cv2.warpPerspective(src, Hs, (1920, 1080), flags=cv2.INTER_AREA)
    rng = np.random.default_rng(0)
    cam = np.clip(cv2.GaussianBlur(cam, (0, 0), 0.8) + rng.normal(0, 3, cam.shape), 0, 255).astype(np.uint8)
    res = ScreenRectifier(L).process(cam)
    assert res.markers_found == 4
    assert res.code.clean and res.code.index == 777
    g = cv2.cvtColor(res.image, cv2.COLOR_BGR2GRAY).astype(float)
    for x, y in pts:
        xs, ys = int(x * res.scale), int(y * res.scale)
        win = np.clip(g[ys - 8:ys + 9, xs - 8:xs + 9] - 40, 0, None)
        yy, xx = np.mgrid[ys - 8:ys + 9, xs - 8:xs + 9]
        cx, cy = (win * xx).sum() / win.sum() / res.scale, (win * yy).sum() / win.sum() / res.scale
        assert abs(cx - x) < 1.0 and abs(cy - y) < 1.0


@pytest.mark.slow
def test_booth_prep_round_trip(tmp_path):
    s = SyntheticLiveSource(width=640, height=360, realtime=False)
    s.open()
    with av.open(str(tmp_path / "clip.mp4"), "w") as c:
        st = c.add_stream("libx264", rate=25)
        st.width, st.height, st.pix_fmt = 640, 360, "yuv420p"
        for _ in range(20):
            for p in st.encode(av.VideoFrame.from_ndarray(s.read().image, format="bgr24")):
                c.mux(p)
        for p in st.encode():
            c.mux(p)
    meta = prepare(tmp_path / "clip.mp4", tmp_path / "booth")
    assert meta["outputs"]["2"]["playback_speed"] == pytest.approx(30 / 2 / 25, rel=1e-3)
    L = Layout(**{k: meta["layout"][k] for k in ("width", "height", "marker", "cell", "margin")})
    for hold in (2, 3):
        idx = []
        with av.open(str(tmp_path / "booth" / f"clip_hold{hold}.mp4")) as c:
            for vf in c.decode(video=0):
                idx.append(read_frame_code(vf.to_ndarray(format="gray"), L).index)
        assert idx == [i // hold for i in range(20 * hold)]
    ts = load_sidecar(tmp_path / "booth" / "clip_codes.csv")
    assert np.allclose(np.diff(ts), 1 / 25, atol=1e-6)
