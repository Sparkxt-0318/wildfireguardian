"""Self-test for the booth demo (no hardware, no window). Run from demo/: python test_demo.py"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lastgasp_demo.__main__ import main  # noqa: E402
from lastgasp_demo.protocol import decode_adv, decode_json, encode_adv, encode_json  # noqa: E402


def test_protocol_roundtrip():
    raw = encode_adv(7, 1234, 3010, 31, 4)
    assert len(raw) == 13
    m = decode_adv(raw)
    assert m == {"v": 1, "id": 7, "seq": 1234, "bat_mv": 3010, "temp_c": 31, "flags": 4}
    assert decode_json(encode_json({**m, "rssi": -60})) is not None
    assert decode_adv(b"\xff\xffXX" + raw[4:]) is None


def test_simulator_detects_spot():
    with tempfile.TemporaryDirectory() as d:
        st = main(["--sim", "--headless", "--duration", "170", "--snapshots", "170", "--out", d])
        assert (Path(d) / "demo_t0170.png").exists()
    village = json.loads((HERE / "village.json").read_text())
    assert int(st.dead.sum()) >= len(village["nodes"]) - 3
    assert len(st.spots) == 1 and st.spots[0]["id"] == 16


if __name__ == "__main__":
    test_protocol_roundtrip()
    test_simulator_detects_spot()
    print("all demo tests passed")
