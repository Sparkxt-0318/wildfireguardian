"""TLV frame parser and stream sync, on synthetic byte frames built here (no hardware data)."""
import math
import struct

import numpy as np
import pytest

from wfgvu import protocol
from wfgvu.drivers import tlv
from wfgvu.drivers.radar_iwr6843 import DEFAULT_CFG, frame_to_data, frames_from_uart_file, load_profile, profile_from_cfg

RNG = np.random.default_rng(42)
N_BINS, N_ANT = 32, 12


def make_frame(n, n_pts=3, with_side=True, n_bins=N_BINS):
    pts = RNG.normal(0, 3, (n_pts, 4)).astype(np.float32)
    rp = RNG.integers(0, 6000, n_bins).astype(np.uint16)
    hm = (RNG.integers(-2000, 2000, (n_bins, N_ANT)) + 1j * RNG.integers(-2000, 2000, (n_bins, N_ANT)))
    side = np.stack([RNG.integers(50, 300, n_pts), RNG.integers(100, 200, n_pts)], axis=1).astype(np.int16)
    tlvs = []
    if n_pts:
        tlvs.append((tlv.TLV_POINTS, tlv.pack_points(pts)))
    tlvs += [(tlv.TLV_RANGE_PROFILE, tlv.pack_range_profile(rp)), (tlv.TLV_AZ_STATIC_HEATMAP, tlv.pack_heatmap(hm))]
    if n_pts and with_side:
        tlvs.append((tlv.TLV_SIDE_INFO, tlv.pack_side_info(side)))
    return tlv.build_frame(n, tlvs, num_obj=n_pts), dict(pts=pts, rp=rp, hm=hm, side=side)


def test_parse_single_frame_values():
    buf, truth = make_frame(5)
    assert len(buf) % 32 == 0
    f = tlv.parse_frame(buf)
    assert f["frame"] == 5 and f["num_obj"] == 3 and f["tlv_types"] == [1, 2, 4, 7]
    assert f["total_len"] == len(buf) and f["platform"] == tlv.DEFAULT_PLATFORM
    assert np.array_equal(f["points"], truth["pts"])
    assert np.array_equal(f["range_profile_q9"], truth["rp"])
    assert np.array_equal(f["az_heatmap"].reshape(N_BINS, N_ANT), truth["hm"].astype(np.complex64))
    assert np.array_equal(f["side_info"], truth["side"])


def test_heatmap_wire_order_is_imag_then_real():
    payload = struct.pack("<hh", 7, -3)            # imag = 7, real = -3
    f = tlv.parse_frame(tlv.build_frame(0, [(tlv.TLV_AZ_STATIC_HEATMAP, payload)]))
    assert f["az_heatmap"][0] == np.complex64(-3 + 7j)


def test_q9_to_db():
    assert tlv.q9_to_db([512])[0] == pytest.approx(20 * math.log10(2))
    assert tlv.q9_to_db([0])[0] == 0.0
    # 512 * log2(1000) counts = 60 dB
    assert tlv.q9_to_db([512 * math.log2(1000)])[0] == pytest.approx(60.0)


def test_bad_magic_and_truncation_raise():
    buf, _ = make_frame(1)
    with pytest.raises(tlv.TLVError):
        tlv.parse_frame(b"\x00" + buf[1:])
    with pytest.raises(tlv.TLVError):
        tlv.parse_frame(buf[:len(buf) - 40])
    with pytest.raises(tlv.TLVError):
        tlv.parse_frame(buf[:20])


def test_tlv_overrun_and_inconsistent_counts_raise():
    good = tlv.build_frame(1, [(tlv.TLV_RANGE_PROFILE, b"\x01\x00" * 4)], pad_to=0)
    # claim a TLV length longer than the packet
    bad = bytearray(good)
    struct.pack_into("<I", bad, tlv.HEADER_LEN + 4, 1000)
    with pytest.raises(tlv.TLVError):
        tlv.parse_frame(bytes(bad))
    # header says 2 objects, points TLV has 1
    pts = tlv.pack_points(np.zeros((1, 4)))
    with pytest.raises(tlv.TLVError):
        tlv.parse_frame(tlv.build_frame(1, [(tlv.TLV_POINTS, pts)], num_obj=2))
    # points TLV length not a multiple of 16
    with pytest.raises(tlv.TLVError):
        tlv.parse_frame(tlv.build_frame(1, [(tlv.TLV_POINTS, b"\x00" * 12)], num_obj=1))
    # absurd totalPacketLen
    hdr = bytearray(good)
    struct.pack_into("<I", hdr, 12, 10 ** 9)
    with pytest.raises(tlv.TLVError):
        tlv.parse_header(bytes(hdr))


def test_framesync_garbage_split_reads_truncated_and_bad_magic():
    frames = [make_frame(i)[0] for i in range(6)]
    stream = (b"\x11\x22garbage" + frames[0] + b"\x99" * 13 + frames[1]
              + frames[2][:100]                       # truncated frame 2 (cut by a UART glitch)
              + frames[3]
              + b"\x02\x01\x04\x03" + b"\x00" * 30    # partial magic, then noise
              + frames[4]
              + bytes([2, 1, 4, 3, 6, 5, 8, 7]) + b"\xff" * 32   # magic + impossible header
              + frames[5])
    sync = tlv.FrameSync()
    out = []
    for k in range(0, len(stream), 7):               # every frame split across many reads
        out += sync.feed(stream[k:k + 7])
    assert [f["frame"] for f in out] == [0, 1, 3, 4, 5]
    assert sync.truncated == 1
    assert sync.garbage_bytes > 0
    assert sync.bad_frames >= 1
    # the recovered frame 3 is bit-exact, i.e. no bytes of frame 2 leaked into it
    assert np.array_equal(out[2]["range_profile_q9"], tlv.parse_frame(frames[3])["range_profile_q9"])


def test_framesync_one_byte_at_a_time_and_bulk_agree():
    data = b"".join(make_frame(i, n_pts=i % 3)[0] for i in range(10))
    s1, s2 = tlv.FrameSync(), tlv.FrameSync()
    a = [f["frame"] for b in range(len(data)) for f in s1.feed(data[b:b + 1])]
    b = [f["frame"] for f in s2.feed(data)]
    assert a == b == list(range(10))
    assert s1.garbage_bytes == 0 and s2.bad_frames == 0


def test_frame_to_data_and_protocol(tmp_path):
    prof = profile_from_cfg(DEFAULT_CFG.read_text())
    buf, truth = make_frame(9, n_bins=prof.n_bins)
    d = frame_to_data(tlv.parse_frame(buf), prof)
    assert d["frame_ok"] and d["n_bins"] == prof.n_bins and d["range_res_m"] == pytest.approx(prof.range_res_m)
    assert d["range_profile_db"][3] == pytest.approx(truth["rp"][3] * tlv.Q9_DB / prof.n_virt, abs=1e-3)
    assert d["points"][0][4] == pytest.approx(truth["side"][0, 0] * 0.1)
    iq = protocol.decode_iq(d["az_heatmap"])
    assert iq.shape == (prof.n_bins, N_ANT) and np.array_equal(iq, truth["hm"].astype(np.complex64))
    msg = protocol.make("reading", unit_id="VU-01", session_id="s", sensor="radar", seq=0, data=d)
    protocol.parse(protocol.dumps(msg))
    # no objects -> empty point list; objects announced but TLV 1 missing -> null + frame not ok
    d0 = frame_to_data(tlv.parse_frame(make_frame(1, n_pts=0, n_bins=prof.n_bins)[0]), prof)
    assert d0["points"] == [] and d0["frame_ok"]
    hdr_only = tlv.build_frame(2, [(tlv.TLV_RANGE_PROFILE, tlv.pack_range_profile([1] * prof.n_bins))], num_obj=4)
    d1 = frame_to_data(tlv.parse_frame(hdr_only), prof)
    assert d1["points"] is None and not d1["frame_ok"]
    # wrong bin count vs config -> frame not ok
    d2 = frame_to_data(tlv.parse_frame(make_frame(3, n_bins=16)[0]), prof)
    assert not d2["frame_ok"]
    # offline re-decode of a raw UART file
    p = tmp_path / "radar_uart.bin"
    p.write_bytes(b"junk" + buf + buf)
    assert [x["frame"] for x in frames_from_uart_file(p, prof)] == [9, 9]


def test_committed_cfg_matches_intent():
    """Default config (long range): >= 50 m, 10 Hz, the laptop's TLVs, and it fits the 921600-baud data UART."""
    prof = load_profile()
    assert prof.max_range_m >= 50.0                       # sees a solid echo behind an ~11 m flame at 10-30 m
    assert prof.range_res_m == pytest.approx(0.4684, abs=1e-3)
    assert prof.n_virt == 12 and prof.n_bins == 128
    assert prof.frame_rate_hz == pytest.approx(10.0)
    assert 60.0 <= prof.start_ghz and prof.sweep_end_ghz <= 64.0
    assert prof.ramp_end_us >= prof.adc_start_us + prof.n_adc / (prof.fs_ksps * 1e3) * 1e6
    assert prof.bytes_per_frame() == 6456
    assert prof.uart_load(921600) == pytest.approx(0.7005, abs=1e-3)
    assert prof.uart_load(921600, points=137) <= 1.0 < prof.uart_load(921600, points=140)
    text = DEFAULT_CFG.read_text()
    assert "guiMonitor -1 1 1 0 1 0 0" in text and "clutterRemoval -1 0" in text
    assert "UNTESTED ON THE EVM" in text


def test_alternative_cfgs():
    """The previous default is kept as _short (22.5 m, over the UART budget at 10 Hz, as its header says);
    _long_fine trades frame rate for ~0.12 m bins."""
    short = load_profile(DEFAULT_CFG.with_name("iwr6843aop_vu_short.cfg"))
    assert 0.04 <= short.range_res_m <= 0.05 and 22.0 <= short.max_range_m <= 23.0
    assert short.n_bins == 512 and short.frame_rate_hz == pytest.approx(10.0)
    assert short.uart_load(921600) > 2.5
    fine = load_profile(DEFAULT_CFG.with_name("iwr6843aop_vu_long_fine.cfg"))
    assert fine.max_range_m >= 50.0 and fine.range_res_m == pytest.approx(0.117, abs=1e-3)
    assert fine.uart_load(921600) < 0.85 and fine.frame_rate_hz < 3.0
    for p in (short, fine):
        assert p.n_virt == 12 and 60.0 <= p.start_ghz and p.sweep_end_ghz <= 64.0


def test_range_profile_is_normalised_by_virtual_antenna_count():
    """PHYS-6: TLV 2 is the SUM over the virtual antennas of log2|x| in Q9 (TI documentation; UNVERIFIED on the EVM).
    A synthetic profile built that way for the 12-antenna default config must come out of the driver at the
    per-antenna dB level (mean 20 log10|x|), not ~12 x it; with no config the antenna count is unknown and the
    driver sends no profile at all (fail closed: such a frame cannot feed the profile path)."""
    prof = profile_from_cfg(DEFAULT_CFG.read_text())
    assert prof.n_virt == 12
    rng = np.random.default_rng(7)
    mag = 10 ** rng.uniform(0.5, 2.5, (prof.n_bins, prof.n_virt))         # |x| per bin per antenna, 10..50 dB
    q9 = np.round(np.log2(mag).sum(axis=1) * 512).astype(np.uint16)      # what the demo sends
    want_db = (20 * np.log10(mag)).mean(axis=1)                          # per-antenna level
    buf = tlv.build_frame(4, [(tlv.TLV_RANGE_PROFILE, tlv.pack_range_profile(q9))], num_obj=0)
    d = frame_to_data(tlv.parse_frame(buf), prof)
    got = np.array(d["range_profile_db"])
    assert d["frame_ok"] and got.shape == (prof.n_bins,)
    assert np.allclose(got, want_db, atol=2e-3)
    # the un-normalised value would be n_virt times larger: e.g. a 12 dB echo-to-noise step reads as 144 dB
    assert np.allclose(tlv.q9_to_db(q9), want_db * prof.n_virt, atol=2e-2)
    assert tlv.q9_to_db([512 * 12], 12)[0] == pytest.approx(20 * math.log10(2))
    with pytest.raises(ValueError):
        tlv.q9_to_db([1], 0)
    # unknown antenna count (no parsed config): no profile; a profile-only frame is then not usable
    d_none = frame_to_data(tlv.parse_frame(buf), None)
    assert d_none["range_profile_db"] is None
    from wfgvu.drivers.radar_iwr6843 import RadarDriver
    ok, why = RadarDriver.assess(None, d_none)
    assert not ok and "range profile" in why
