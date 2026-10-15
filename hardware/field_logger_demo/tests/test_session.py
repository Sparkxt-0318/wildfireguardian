"""Loading sessions and their integrity (spec section 6 time base and test 4)."""
import shutil

import pytest

from app import library, privacy, replay, session, stops
from app.vendor import usb_export as ux
from conftest import ROOT, SAMPLES
from fakes import logger_double as fx
from fakes.tracks import build, to_wfg

SIM_FILES = sorted((ROOT / "sessions" / "sim").glob("*.wfg"))
SAMPLE_WFG = sorted(SAMPLES.glob("*.wfg")) if SAMPLES.exists() else []


def _csv_utc(data):
    """utc_est (column 8) of every row of usb_export.to_csv(), as epoch ms."""
    out = []
    for line in ux.to_csv(data).splitlines()[1:]:
        c = line.split(",")
        out.append(session._iso_ms(c[7]) if c[7] else None)
    return out


def _files():
    rows = build([("stop", 60, 0.8), ("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3), ("stop", 30, 0.8)])
    yield "clock_jump", to_wfg(rows, jump_at_t=130.0)
    yield "recovered", fx.recovered()
    yield "indoor_filler", fx.indoor_filler()
    for p in SIM_FILES + SAMPLE_WFG:
        yield p.name, p.read_bytes()


@pytest.mark.parametrize("name,data", list(_files()), ids=lambda v: v if isinstance(v, str) else "")
def test_utc_est_matches_usb_export_to_csv(name, data):
    assert session.utc_est_series(data) == _csv_utc(data), name


def test_utc_est_with_a_corrupted_record_matches_too():
    data = bytearray(fx.outdoor_fix())
    data[20 * ux.REC + 30] ^= 0x55
    assert session.utc_est_series(bytes(data)) == _csv_utc(bytes(data))


def _corrupted(src, k=50):
    data = bytearray(src.read_bytes())
    data[k * ux.REC + 30] ^= 0x5A
    return bytes(data)


def _payload_for(tmp_root, name, data):
    from app import config
    d = config.REAL_DIR / "itest"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)
    return replay.build(library.entry_for_file("real/itest/" + name))


def test_corrupted_record_is_kept_and_marked(tmp_root):
    src = ROOT / "sessions" / "sim" / "sim_walk_4_crossings.wfg"
    data = _corrupted(src)
    s = session.load_wfg_bytes(data, "S000101.wfg")
    assert len(s.records) == len(data) // ux.REC                 # nothing dropped
    assert s.records[50]["type"] == "CORRUPT" and not s.records[50]["ok"]
    assert s.integrity["status"] == "CORRUPT" and s.integrity["crc_errors"] == 1
    p = _payload_for(tmp_root, "S000101.wfg", data)
    r = p["records"][50]
    raw = data[50 * 48:51 * 48].hex()                            # shown, with its position bytes and CRC masked
    assert r["ok"] == 0 and r["ty"] == "CORRUPT" and r["hx"] == privacy.mask_hex(raw, "FIX") and r["hx"] != raw
    assert p["meta"]["n_rec"] == len(s.records) and p["meta"]["crc_ok"] == len(s.records) - 1
    num = replay.summary_numbers(p)
    assert num["records"] - num["records_crc_ok"] == 1
    # the analysis still runs on every readable row
    assert len(p["stops"]) == len(replay.build(library.entry_for_file("sim/sim_walk_4_crossings.wfg"))["stops"])


def test_missing_seq_is_reported_not_repaired(tmp_root):
    src = (ROOT / "sessions" / "sim" / "sim_walk_4_crossings.wfg").read_bytes()
    data = src[:60 * ux.REC] + src[61 * ux.REC:]                 # record #60 is gone
    s = session.load_wfg_bytes(data, "S000102.wfg")
    assert s.integrity["seq_errors"] > 0 and s.integrity["status"] == "CORRUPT"
    p = _payload_for(tmp_root, "S000102.wfg", data)
    gaps = [r for r in p["records"] if r.get("sg")]
    assert len(gaps) == 1 and gaps[0]["sg"] == [59, 61, 1] and gaps[0]["i"] == 60
    assert p["meta"]["seq_breaks"] == 1 and p["meta"]["seq_missing"] == 1
    assert replay.summary_numbers(p)["records_missing"] == 1
    assert all(r["ok"] for r in p["records"])                      # every record is still readable


def test_clean_files_report_no_seq_break(tmp_root):
    for p in SIM_FILES:
        pay = replay.build(library.entry_for_file("sim/" + p.name))
        assert pay["meta"]["seq_breaks"] == 0 and pay["meta"]["crc_ok"] == pay["meta"]["n_rec"], p.name


def test_csv_source_gives_the_same_rows_and_stops_as_the_wfg(tmp_path):
    wfg = SAMPLES / "S000001_WALK.wfg"
    if not wfg.exists():
        pytest.skip("sample sessions not available")
    csv_path = tmp_path / "S000001_WALK.csv"
    csv_path.write_text(ux.to_csv(wfg.read_bytes(), wfg.name), encoding="utf-8")
    a, b = session.load_wfg(wfg), session.load_csv(csv_path)
    assert len(a.rows) == len(b.rows) and len(a.events) == len(b.events) and len(a.records) == len(b.records)
    for x, y in zip(a.rows, b.rows):
        assert x["mono"] == y["mono"] and x["fix"] == y["fix"] and x["utc_ms"] == y["utc_ms"]
        if x["fix"]:
            assert abs(x["lat"] - y["lat"]) < 1e-9 and abs(x["lon"] - y["lon"]) < 1e-9
    assert b.integrity["ok"] and b.integrity["seq_errors"] == 0
    ra, rb = stops.analyse(a.rows, a.mode), stops.analyse(b.rows, b.mode)
    assert [(s["t0"], s["t1"]) for s in ra["stops"]] == [(s["t0"], s["t1"]) for s in rb["stops"]]
    assert a.sid == b.sid and a.mode == b.mode


def test_sample_csv_files_load(tmp_path):
    if not SAMPLES.exists():
        pytest.skip("sample sessions not available")
    for p in sorted(SAMPLES.glob("*.csv")):
        s = session.load_csv(p)
        assert s.records and s.sid.startswith("WFG-"), p.name


def test_gpx_is_development_data_never_device_data(tmp_root):
    gpx = SAMPLES / "S000001_WALK.gpx"
    if not gpx.exists():
        pytest.skip("sample GPX not available")
    from app import config
    dst = config.SESSIONS / "dev"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(gpx, dst / "phone.gpx")
    p = replay.build(library.entry_for_file("dev/phone.gpx"))
    assert p["meta"]["source"] == "gpx" and p["meta"]["device"] == "-" and p["meta"]["device_id"] is None
    assert p["meta"]["sid"].startswith("GPX-")
    # a GPX file has no record bytes: no CRC is claimed on the page, the summary or summary.json
    assert p["meta"]["has_crc"] is False and p["meta"]["crc_ok"] is None and p["meta"]["n_rec"] > 10
    num = replay.summary_numbers(p)
    assert num["source"] == "gpx" and num["device_recording"] is False and num["records_crc_ok"] is None
    # for comparison: a SIM recording has records with a CRC, and is not a device recording either
    sim = replay.build(library.entry_for_file("sim/sim_walk_4_crossings.wfg"))
    assert sim["meta"]["has_crc"] is True and sim["meta"]["crc_ok"] == sim["meta"]["n_rec"]
    ns = replay.summary_numbers(sim)
    assert ns["source"] == "wfg" and ns["device_recording"] is False and ns["simulated"] is True
