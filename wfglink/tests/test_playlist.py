"""Booth playback (io/playlist.py): playlist files, segments and roi, real-time pacing with
late frames skipped, skipping a missing or broken clip, the synthetic fallback and pause.
Also FileSource timestamps, which file mode and the validation rely on."""
import time
from pathlib import Path

import av
import numpy as np
import pytest

from wfglink import PROJECT_ROOT
from wfglink.io.playlist import PlaybackConfig, Player, PlayItem, PlaylistError, clip_item, load_playlist, roi_pixels
from wfglink.io.sources import FileSource


def _clip(path: Path, n: int = 30, fps: int = 30, size: tuple[int, int] = (320, 180)) -> Path:
    """A small H.264 clip; frame i has a bright square at x = 4 i (so frames are told apart)."""
    w, h = size
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = w, h, "yuv420p"
        for i in range(n):
            img = np.full((h, w, 3), 20, np.uint8)
            img[h // 2 - 4: h // 2 + 4, (4 * i) % (w - 8): (4 * i) % (w - 8) + 8] = 230
            for pkt in s.encode(av.VideoFrame.from_ndarray(img, format="bgr24")):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)
    return path


def _collect(player: Player, seconds: float, until=None) -> list:
    """Frames as a consumer sees them (the newest one, polled every 5 ms)."""
    out, last, t_end = [], None, time.monotonic() + seconds
    while time.monotonic() < t_end:
        f = player.latest()
        if f is not None and f.index != last:
            last = f.index
            out.append(f)
            if until is not None and until(out):
                break
        time.sleep(0.005)
    return out


def test_file_source_true_timestamps_and_loop(tmp_path):
    clip = _clip(tmp_path / "c.mp4", n=10, fps=25)
    src = FileSource(clip, loop=True)
    src.open()
    times = [src.read().t for _ in range(25)]
    src.close()
    d = np.diff(times)
    assert np.allclose(d, 1 / 25, atol=1e-6)  # strictly increasing across the loop seam
    assert times[0] == pytest.approx(0.0, abs=1e-6)


def test_playlist_entries_segments_labels_and_credits(tmp_path):
    (tmp_path / "data" / "clips").mkdir(parents=True)
    (tmp_path / "data" / "clips.csv").write_text("clip_id,title,credit_line\nA1,Clip A title,Credit: Someone\n")
    (tmp_path / "data" / "clips" / "A1.yaml").write_text(
        "clip_id: A1\nfile: data/raw/a1.mp4\nroi: [0.0, 0.0, 0.5, 1.0]\nsegments_s: [[1.0, 2.0], [3.0, null]]\n"
        "gate: [0.5, 0.1, 0.5, 0.9]\n")
    pl = tmp_path / "playlist.yaml"
    pl.write_text("clips:\n  - clip: A1\n  - clip: A1\n    segments_s: [[0.5, 1.5]]\n    label: Short A\n"
                  "  - B2\n  - clip: data/raw/c3.mp4\n")
    a, a2, b, c = load_playlist(pl, root=tmp_path)
    assert (a.key, a.path, a.roi, a.gate) == ("A1", tmp_path / "data/raw/a1.mp4", [0.0, 0.0, 0.5, 1.0], [0.5, 0.1, 0.5, 0.9])
    assert a.segments == [(1.0, 2.0), (3.0, None)]
    assert (a.label, a.credit) == ("Clip A title", "Credit: Someone")
    assert a2.segments == [(0.5, 1.5)] and a2.label == "Short A"          # per-entry override
    assert b.error and b.path is None                                     # no settings file: skipped when played
    assert c.error                                                        # a video that does not exist (yet)
    (tmp_path / "bad.yaml").write_text("clips: 3\n")
    with pytest.raises(PlaylistError):
        load_playlist(tmp_path / "bad.yaml", root=tmp_path)
    with pytest.raises(PlaylistError):
        load_playlist(tmp_path / "nothing.yaml", root=tmp_path)
    with pytest.raises(PlaylistError):
        clip_item("A1", root=tmp_path, segments=[[2.0, 1.0]])


def test_the_booth_playlist_names_the_approved_clips():
    items = load_playlist(PROJECT_ROOT / "booth" / "playlist.yaml")
    assert [i.key for i in items] == ["C5_nist_emberometer", "C6_nist_dragon"]
    for i in items:
        assert not i.error and i.path == PROJECT_ROOT / "data" / "raw" / f"{i.key}.mp4"
        assert i.credit == "Credit: NIST" and i.label
    assert items[1].segments == [(17.05, 22.55)]        # C6: the NIST lab part only


def test_roi_pixels():
    assert roi_pixels(None, 640, 360) == (0, 0, 640, 360)
    assert roi_pixels([0.0, 0.0, 0.5, 1.0], 640, 360) == (0, 0, 320, 360)
    assert roi_pixels([10, 20, 110, 220], 640, 360) == (10, 20, 110, 220)
    assert roi_pixels([0.5, 0.5, 0.5, 0.9], 640, 360) == (0, 0, 640, 360)    # empty: the whole frame


@pytest.mark.slow
def test_plays_segments_cropped_in_real_time_and_skips_a_missing_clip(tmp_path):
    a = _clip(tmp_path / "a.mp4", n=30, size=(640, 360))
    b = _clip(tmp_path / "b.mp4", n=15)
    items = [PlayItem("A", a, [(0.2, 0.6)], roi=[0.0, 0.0, 0.5, 1.0], label="Clip A", credit="Credit: A"),
             PlayItem("gone", tmp_path / "gone.mp4"), PlayItem("B", b, label="Clip B")]
    lines = []
    p = Player(items, PlaybackConfig(max_width=200, cut_gap_s=1.0), log=lines.append)
    t0 = time.monotonic()
    p.start()
    try:
        frames = _collect(p, 15, until=lambda fs: fs[-1].meta["loop"] >= 2)
    finally:
        p.stop()
    wall = time.monotonic() - t0
    seen_a = [f for f in frames if f.meta["clip"] == "A"]
    seen_b = [f for f in frames if f.meta["clip"] == "B"]
    assert seen_a and seen_b
    # A plays only over its segment, cropped to the left half and scaled to max_width.
    assert all(0.2 - 1e-6 <= f.meta["clip_t"] < 0.6 for f in seen_a)
    assert seen_a[0].image.shape == (225, 200, 3)
    assert seen_b[0].image.shape[:2] == (112, 200)                    # whole frame, scaled to max_width
    assert (seen_a[0].meta["label"], seen_a[0].meta["credit"]) == ("Clip A", "Credit: A")
    # Times only increase; every cut adds the gap; each clip start is a new item.
    t = np.array([f.t for f in frames])
    assert np.all(np.diff(t) > 0)
    cuts = [k for k in range(1, len(frames)) if frames[k].meta["item"] != frames[k - 1].meta["item"]]
    assert len(cuts) >= 3 and all(frames[k].t - frames[k - 1].t >= 1.0 for k in cuts)
    # Real time: two passes of 0.4 s + 0.5 s of video take about that long, not as long as decoding allows.
    assert wall > 1.5
    # The missing clip is skipped on every loop, with one log line for the same reason.
    assert sum(e["event"] == "skipped" and e["clip"] == "gone" for e in p.events) >= 2
    assert len([ln for ln in lines if "gone" in ln]) == 1


@pytest.mark.slow
def test_a_broken_clip_is_skipped_and_nothing_playable_gives_synthetic_video(tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video" * 100)
    lines = []

    def synthetic():
        from wfglink.io.synthetic_live import SyntheticLiveSource

        return SyntheticLiveSource(width=160, height=96, realtime=False, seed=1)

    p = Player([PlayItem("broken", broken), PlayItem("gone", tmp_path / "gone.mp4")], PlaybackConfig(retry_s=1.0),
               synthetic=synthetic, log=lines.append)
    p.start()
    try:
        frames = _collect(p, 4.0)
    finally:
        p.stop()
    assert frames and all(f.meta["synthetic"] and f.meta["clip"] == "synthetic" for f in frames)
    assert len({f.meta["item"] for f in frames}) == 1               # retries do not restart the synthetic video
    assert sum(e["event"] == "failed" and e["clip"] == "broken" for e in p.events) >= 2   # tried again after retry_s
    assert any("no playable clip" in ln for ln in lines)


@pytest.mark.slow
def test_pause_holds_the_picture_and_stops_the_clock(tmp_path):
    a = _clip(tmp_path / "a.mp4", n=90)
    p = Player([PlayItem("A", a)])
    p.start()
    try:
        before = _collect(p, 1.0)
        p.pause()
        time.sleep(0.1)
        held = p.latest()
        time.sleep(1.0)
        assert p.latest() is held and p.paused                       # nothing new while paused
        p.resume()
        after = _collect(p, 0.5)
    finally:
        p.stop()
    assert before and after
    # Playback continues where it stopped: the paused second is not skipped.
    assert after[0].meta["clip_t"] - held.meta["clip_t"] < 0.2
    assert [e["event"] for e in p.events if e["event"] in ("paused", "resumed")] == ["paused", "resumed"]


def test_late_frames_are_dropped_while_that_catches_up_else_the_clock_restarts():
    p = Player([], PlaybackConfig(late_frames=1.0, resync_s=0.5))
    dt = 1 / 30
    now = time.monotonic()
    p._anchor = [now, 0.0]
    assert p._on_time(0.0, dt, droppable=True)                       # on time
    p._anchor = [time.monotonic() - 0.3, 0.0]
    assert not p._on_time(0.0, dt, droppable=True)                   # 0.3 s late: dropped
    assert not p._on_time(0.2, dt, droppable=True)                   # 0.1 s late and catching up: dropped
    assert p._on_time(0.2, dt, droppable=True)                       # not catching up: the clock restarts
    assert p.stats["late"] == 2 and p.stats["resyncs"] == 1
    p._anchor = [time.monotonic() - 2.0, 0.0]
    assert p._on_time(0.0, dt, droppable=True)                       # far behind: restart, do not drop for seconds
    p._anchor = [time.monotonic() - 0.3, 0.0]
    assert p._on_time(0.0, dt, droppable=False)                      # synthetic video: never dropped
    assert p.stats["resyncs"] == 3


@pytest.mark.slow
def test_a_slow_consumer_skips_frames_and_the_picture_does_not_lag(tmp_path):
    a = _clip(tmp_path / "a.mp4", n=90)
    p = Player([PlayItem("A", a)])
    p.start()
    try:
        got, t_end = [], time.monotonic() + 2.0
        while time.monotonic() < t_end:
            f = p.latest()
            if f is not None and (not got or f.index != got[-1][0].index):
                got.append((f, time.monotonic()))
                time.sleep(0.15)                                     # an analysis 5 times slower than the video
            else:
                time.sleep(0.005)
    finally:
        p.stop()
    idx = [f.index for f, _ in got]
    assert max(np.diff(idx)) >= 3                                    # frames were skipped, not queued
    (f0, w0), (f1, w1) = got[1], got[-1]
    assert abs((f1.t - f0.t) - (w1 - w0)) < 0.35                     # the newest frame keeps pace with the clock


def test_clips_csv_rows_have_every_column():
    """Every row of data/clips.csv parses into exactly the header's columns, with a credit line.

    A field holding a comma must be quoted; an unquoted one shifts every later column and the
    booth would show part of a licence note as the credit."""
    import csv

    with open(PROJECT_ROOT / "data" / "clips.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    header = rows[0]
    for r in rows[1:]:
        assert len(r) == len(header), (r[0], len(r), len(header))
        d = dict(zip(header, r))
        assert d["credit_line"].strip() and d["license"].strip(), d["clip_id"]
