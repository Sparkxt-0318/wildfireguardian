"""Consistency tests for hardware/vehicle-unit/docs and README.md (no hardware, no network, deterministic).

Run:  cd hardware/vehicle-unit && <venv>/bin/python -m pytest docs/test_docs.py

What is checked:
- the committed SVGs and the HOUSING.md checks block equal what make_drawings.py generates; both SVGs are
  well-formed with a title/description;
- wiring: make_drawings.PIN_MAP is exactly the user's printed build-manual pin map (USER_MAP); the WIRING.md pin
  table equals PIN_MAP; config/unit.yaml (SPI buses/devices, software CS GPIO, I2C, disc limit, camera id) agrees;
  every "GPIOn ... pin m" pairing in the docs, the drawing and unit.yaml is physically right on the J8 header; no doc
  mentions the withdrawn second-SPI-bus wiring or the old BNO055 pins (except in an explicit negation);
- housing: the drawing only carries the user's numbers; unit.yaml housing / sensor offsets equal them; the computed
  checks do not depend on the sign of the x offsets; housing.scad is gone;
- README "First run": the four command blocks are present in order, and every module, flag and path they name
  exists (wfgvu.tccheck, python -m wfgvu --help, run_crossing.sh / crossing --pi, --replay);
- the README keeps the 'Not verified on hardware' section and the single allowed claim; BOM prices are blank; no
  folder under hardware/ is named 'logs' or 'devices'.
What is NOT checked: anything physical. These are documents.
"""
from __future__ import annotations

import ast
import importlib.util
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parent
VU = DOCS.parent
HARDWARE = VU.parent
REPO = HARDWARE.parent
CROSSING = REPO / "apps" / "crossing"
SVG_NS = "{http://www.w3.org/2000/svg}"
ALLOWED_CLAIM = "vehicle-mountable unit, tested on a car and on lab flames, ready for a fire-service trial"


def _load_make_drawings():
    spec = importlib.util.spec_from_file_location("vu_make_drawings", DOCS / "make_drawings.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MD = _load_make_drawings()


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _svg_text(name: str) -> str:
    root = ET.parse(DOCS / name).getroot()
    return "\n".join((t.text or "") for t in root.iter(SVG_NS + "text"))


# ------------------------------------------------------------------ generated outputs
def test_svgs_are_up_to_date():
    for name, text in MD.outputs().items():
        assert (DOCS / name).read_text(encoding="utf-8") == text, "%s is stale: run docs/make_drawings.py" % name


def test_housing_md_checks_block_is_up_to_date():
    h = _read("HOUSING.md")
    assert MD.housing_md_with_checks(h) == h, "HOUSING.md checks block is stale: run docs/make_drawings.py"
    assert MD.checks_markdown() in h


def test_generation_is_deterministic():
    assert MD.outputs() == MD.outputs()
    assert MD.checks_markdown() == MD.checks_markdown()


@pytest.mark.parametrize("name", ["wiring.svg", "housing.svg"])
def test_svg_well_formed_and_accessible(name):
    root = ET.parse(DOCS / name).getroot()
    assert root.tag == SVG_NS + "svg"
    assert root.get("viewBox") and root.get("role") == "img"
    assert root.find(SVG_NS + "title").text.strip()
    assert len(root.find(SVG_NS + "desc").text) > 40
    w, h = (float(v) for v in root.get("viewBox").split()[2:])
    for el in root.iter():
        for attr in ("x", "x1", "x2", "cx"):
            if el.get(attr) is not None:
                assert -1 <= float(el.get(attr)) <= w + 1, (name, el.tag, attr, el.get(attr))
        for attr in ("y", "y1", "y2", "cy"):
            if el.get(attr) is not None:
                assert -1 <= float(el.get(attr)) <= h + 1, (name, el.tag, attr, el.get(attr))
        if el.tag == SVG_NS + "text":
            assert float(el.get("font-size")) >= 9.5, "text too small to read"


# ------------------------------------------------------------------ (a) the user's pin map everywhere
GPIO_TO_PIN = {int(v.split()[0][4:]): p for p, v in MD.PI_PINS.items() if v.startswith("GPIO")}


def test_header_pinout_constants():
    # fixed Raspberry Pi J8 facts the whole page relies on
    assert len(MD.PI_PINS) == 40
    assert sum(1 for v in MD.PI_PINS.values() if v == "GND") == 8
    assert MD.PI_PINS[1] == "3V3" and MD.PI_PINS[17] == "3V3"
    assert MD.PI_PINS[6] == "GND" and MD.PI_PINS[20] == "GND"
    for pin, gpio in ((3, 2), (5, 3), (19, 10), (21, 9), (23, 11), (24, 8), (26, 7), (29, 5), (8, 14), (10, 15)):
        assert GPIO_TO_PIN[gpio] == pin, (gpio, pin)


def test_pin_map_is_the_users_map():
    u = MD.USER_MAP
    expect = {
        u["max31855_3v3_pin"]: "3V3", u["max31855_gnd_pin"]: "GND", u["max31855_clk"][0]: "SCLK",
        u["max31855_do"][0]: "MISO", u["cs_plate"][0]: "CS_PLATE", u["cs_housing"][0]: "CS_HOUSING",
        u["cs_air"][0]: "CS_AIR", u["bno055_3v3_pin"]: "3V3", u["bno055_gnd_pin"]: "GND", u["bno055_sda_pin"]: "SDA",
        u["bno055_scl_pin"]: "SCL",
    }
    assert {p: n for p, (n, _l) in MD.USED_PINS.items()} == expect
    # the GPIO numbers the user gave sit on the pins the user gave
    for key in ("max31855_clk", "max31855_do", "cs_plate", "cs_housing", "cs_air"):
        pin, gpio = u[key]
        assert GPIO_TO_PIN[gpio] == pin, key
    # the literal facts, so a change to USER_MAP itself also fails
    assert (u["max31855_3v3_pin"], u["max31855_gnd_pin"], u["max31855_clk"], u["max31855_do"]) == (17, 20, (23, 11),
                                                                                                  (21, 9))
    assert (u["cs_plate"], u["cs_housing"], u["cs_air"]) == ((24, 8), (26, 7), (29, 5))
    assert (u["bno055_3v3_pin"], u["bno055_gnd_pin"], u["bno055_sda_pin"], u["bno055_scl_pin"]) == (1, 6, 3, 5)
    goes = {p: to for p, _n, to, _l in MD.PIN_MAP}
    assert "BNO055" in goes[1] and "BNO055" in goes[6] and "MAX31855" in goes[17] and "MAX31855" in goes[20]
    assert "tc_plate" in goes[24] and "tc_housing" in goes[26] and "tc_air" in goes[29]


def _wiring_pin_rows():
    rows = {}
    for line in _read("WIRING.md").splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([A-Z0-9_]+)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            rows[int(m.group(1))] = (m.group(2), m.group(3), m.group(4))
    return rows


def test_wiring_md_pin_table_matches_pin_map():
    rows = _wiring_pin_rows()
    assert set(rows) == set(MD.USED_PINS), (sorted(rows), sorted(MD.USED_PINS))
    goes = {p: to for p, _n, to, _l in MD.PIN_MAP}
    for pin, (signal, net, to) in rows.items():
        assert net == MD.USED_PINS[pin][0], (pin, net)
        assert MD.PI_PINS[pin].split()[0] in signal, (pin, signal, MD.PI_PINS[pin])
        assert to == goes[pin], (pin, to, goes[pin])
    w = _read("WIRING.md")
    assert MD.PIN_MAP_SOURCE in w


def test_wiring_svg_labels_every_used_pin_and_net():
    txt = _svg_text("wiring.svg")
    for pin, (net, label) in MD.USED_PINS.items():
        assert re.search(r"(^|\n)%d(\n|$)" % pin, txt), "pin number %d not labelled" % pin
        assert label in txt
        assert MD.NETS[net][2] in txt, "legend lacks %s" % net
    for must in ("0x28", "i2c_arm_baudrate=10000", "115200", "921600", "5 A blade fuse", "TVS", "+ yellow", "- red",
                 "no_cs", "GPIO5", "software", "InfiRay P2 Pro", "0bda:5830", "3V3 pin 1, GND pin 6",
                 "SDA pin 3, SCL pin 5", "3V3 pin 17", "GND pin 6 -> BNO055 GND", "70 C",
                 "Pin map from the user's printed build manual (2026-11-17)"):
        assert must in txt, must


# "GPIO8, pin 24", "GPIO9 MISO pin 21", "GPIO5 (pin 29"; and "pin 23 (GPIO11)". Never across ")", ";", "|" or a
# second comma, so "CLK pin 23 (GPIO11), DO pin 21" pairs GPIO11 with pin 23 only.
_PAIR_RES = (re.compile(r"GPIO\s?(\d+)(?:,\s*|[^\d,;|)]{0,25}?)\bpin\s(\d+)"),
             re.compile(r"\bpin\s(\d+)\s*[,(]?\s*GPIO\s?(\d+)"))


def _pin_pairs(text: str):
    for line in text.splitlines():
        for m in _PAIR_RES[0].finditer(line):
            yield int(m.group(1)), int(m.group(2)), line
        for m in _PAIR_RES[1].finditer(line):
            yield int(m.group(2)), int(m.group(1)), line


def _pairing_sources():
    out = {"wiring.svg": _svg_text("wiring.svg")}
    for n in ("WIRING.md", "HOUSING.md", "BOM.md", "MOUNTING_AND_POWER.md"):
        out[n] = _read(n)
    for rel in ("README.md", "DESIGN.md", "config/unit.yaml", "system/README.md"):
        p = VU / rel
        if p.is_file():
            out[rel] = p.read_text(encoding="utf-8")
    return out


def test_every_gpio_pin_pairing_is_physically_right():
    n = 0
    for src, text in _pairing_sources().items():
        for gpio, pin, line in _pin_pairs(text):
            n += 1
            assert GPIO_TO_PIN.get(gpio) == pin, "%s: GPIO%d is pin %s, not pin %d: %s" % (
                src, gpio, GPIO_TO_PIN.get(gpio), pin, line.strip())
    assert n >= 20, "too few GPIO/pin pairs found (%d): the pairing regex no longer matches the docs" % n


# withdrawn wiring: tc_air on a second SPI bus (GPIO18/19/21, pins 12/35/40) or on GPIO25 (pin 22); BNO055 on pin 9/17
_OLD = re.compile(r"spi1-1cs|\bSPI1\b|spidev1|GPIO\s?18\b|GPIO\s?25\b|\bpin\s(?:9|12|22|35|40)\b|"
                  r"BNO055[^\n]{0,40}pin 17|pin 17[^\n]{0,20}BNO055")
_NEGATION = re.compile(r"\b(no|not|never|remove|removed|withdrawn)\b", re.I)


def _all_docs():
    files = []
    for root in (VU, CROSSING):
        if not root.is_dir():
            continue
        for p in root.rglob("*.md"):
            if any(part in (".venv", "node_modules", "vendor", "__pycache__", ".pytest_cache") for part in p.parts):
                continue
            files.append(p)
    files.append(VU / "config" / "unit.yaml")
    return [f for f in files if f.is_file()]


def test_no_doc_mentions_the_withdrawn_wiring():
    bad = []
    for f in _all_docs():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _OLD.search(line) and not _NEGATION.search(line):
                bad.append("%s:%d: %s" % (f.relative_to(REPO), i, line.strip()[:120]))
    assert not bad, "old pin design still mentioned:\n" + "\n".join(bad)
    # the drawing: GPIO18 / GPIO25 may appear only as the grey label of an unused header pin
    root = ET.parse(DOCS / "wiring.svg").getroot()
    for t in root.iter(SVG_NS + "text"):
        s = t.text or ""
        if _OLD.search(s):
            assert s in ("GPIO18", "GPIO25") and t.get("fill") == "#999", s


def _unit_yaml():
    yaml = pytest.importorskip("yaml")
    p = VU / "config" / "unit.yaml"
    if not p.is_file():
        pytest.skip("config/unit.yaml not present")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_unit_yaml_spi_matches_the_users_map():
    s = _unit_yaml()["sensors"]
    u = MD.USER_MAP
    assert (int(s["tc_plate"]["spi_bus"]), int(s["tc_plate"]["spi_dev"])) == (0, 0)       # CE0 = GPIO8 pin 24
    assert (int(s["tc_housing"]["spi_bus"]), int(s["tc_housing"]["spi_dev"])) == (0, 1)   # CE1 = GPIO7 pin 26
    assert (int(s["tc_air"]["spi_bus"]), int(s["tc_air"]["spi_dev"])) == (0, 0)
    assert int(s["tc_air"]["cs_gpio"]) == u["cs_air"][1]
    assert GPIO_TO_PIN[int(s["tc_air"]["cs_gpio"])] == u["cs_air"][0]
    for name in ("tc_plate", "tc_housing"):
        assert "cs_gpio" not in s[name] or s[name]["cs_gpio"] is None, name
    assert float(s["tc_plate"]["disc_max_c"]) == 70.0
    w = _read("WIRING.md")
    for row in ("| `tc_plate` | `spi_bus`, `spi_dev` | 0, 0 |", "| `tc_housing` | `spi_bus`, `spi_dev` | 0, 1 |",
                "| `tc_air` | `spi_bus`, `spi_dev`, `cs_gpio` | 0, 0, 5 |", "| `tc_plate` | `disc_max_c` | 70"):
        assert row in w, "WIRING.md section 8 lacks: " + row


def test_unit_yaml_i2c_camera_radar_match_wiring():
    s = _unit_yaml()["sensors"]
    assert int(s["imu"]["i2c_bus"]) == 1 and int(s["imu"]["address"]) == 0x28
    assert int(s["radar"]["cli_baud"]) == 115200 and int(s["radar"]["data_baud"]) == 921600
    assert s["thermal"]["model"] == "InfiRay P2 Pro"
    assert str(s["thermal"]["usb_id"]).lower() == "0bda:5830"
    assert str(s["thermal"]["index"]) == "auto" or isinstance(s["thermal"]["index"], int)
    w = _read("WIRING.md")
    assert "| `imu` | `i2c_bus`, `address` | 1, 0x28 |" in w
    assert '| `thermal` | `model`, `usb_id`, `index` | "InfiRay P2 Pro", "0bda:5830", auto |' in w


def test_unit_yaml_comments_name_the_users_pins():
    t = (VU / "config" / "unit.yaml").read_text(encoding="utf-8")
    for s in ("GPIO5", "pin 29", "GPIO8", "GPIO7", "pin 1", "pin 6", "pin 3", "pin 5"):
        assert s in t, s


# ------------------------------------------------------------------ housing (supplied, documented only)
def test_unit_yaml_housing_and_offsets_equal_the_users_numbers():
    cfg = _unit_yaml()
    h = cfg["housing"]
    for k, v in MD.SUPPLIED.items():
        got = h[k]
        if isinstance(v, tuple):
            assert [float(x) for x in got] == [float(x) for x in v], k
        elif isinstance(v, dict):
            for kk, vv in v.items():
                assert got[kk] == vv, (k, kk)
        elif isinstance(v, str):
            assert str(got).startswith(v), k
        else:
            assert float(got) == float(v), k
    offs = cfg["mount"]["sensor_offsets_mm"]
    assert set(offs) == set(MD.SENSOR_OFFSETS_MM)
    for name, d in MD.SENSOR_OFFSETS_MM.items():
        for k, v in d.items():
            assert float(offs[name][k]) == float(v), (name, k)


def test_housing_svg_draws_only_the_given_numbers_and_says_so():
    txt = _svg_text("housing.svg")
    for must in (MD.HOUSING_LABEL, "FRONT VIEW", "PLAN VIEW", "plate 172 x 66 x 3", "body 180", "140", "72", "34",
                 "dia 12", "52", "42", "thinned to 1.2", "dia 30.6", "x = -52", "x = -8", "x = +45", "gap 10 mm",
                 "UNCONFIRMED", "58 x 49", "M3 pilot holes every 10 mm", "4 mm walls", "PETG", "70 C"):
        assert must in txt, must
    for gone in ("radome", "Ge", "magnet", "germanium", "PTFE", "base plate"):
        assert gone not in txt, gone


def test_scad_and_concept_are_gone():
    assert not (DOCS / "housing.scad").exists()
    for f in [DOCS / n for n in ("WIRING.md", "HOUSING.md", "BOM.md", "MOUNTING_AND_POWER.md")] + [VU / "README.md"]:
        t = f.read_text(encoding="utf-8")
        assert "housing.scad" not in t or "deleted" in t, f.name
    h = _read("HOUSING.md")
    assert "not a design" in h and "Checks on the supplied housing (questions, not changes)" in h
    for item in ("**(a)", "**(b)", "**(c)", "**(d)", "**(e)"):
        assert item in h, item
    assert "calculation" in h.lower()


def test_checks_do_not_depend_on_the_x_sign(monkeypatch):
    base = MD.checks()
    flipped = {k: dict(v, x=-v["x"]) for k, v in MD.SENSOR_OFFSETS_MM.items()}
    monkeypatch.setattr(MD, "SENSOR_OFFSETS_MM", flipped)
    assert MD.checks() == base
    assert MD.checks_markdown() == MD.checks_markdown()


def test_check_arithmetic():
    # slab: lossless energy balance; half-wave thickness reflects nothing; numbers quoted in the text
    for eps in (2.6, 3.0):
        R, T = MD.slab_rt(eps, 0.0, 1.2, 60.27e9)
        assert R + T == pytest.approx(1.0, abs=1e-12)
        hw = MD.radome_thickness_mm(eps, 60.275e9)
        R0, _ = MD.slab_rt(eps, 0.0, hw, 60.275e9)
        assert R0 < 1e-12
    assert MD.radome_thickness_mm(2.6, 60.275e9) == pytest.approx(1.544, abs=0.002)
    assert MD.radome_thickness_mm(3.0, 60.275e9) == pytest.approx(1.436, abs=0.002)
    # view factor: limits and reciprocity A1 F12 = A2 F21
    assert MD.disc_view_factor(15.0, 1e6, 10.0) == pytest.approx(1.0, abs=1e-6)
    f12 = MD.disc_view_factor(15.0, 25.0, 10.0)
    f21 = MD.disc_view_factor(25.0, 15.0, 10.0)
    assert 15.0 ** 2 * f12 == pytest.approx(25.0 ** 2 * f21, rel=1e-9)
    assert MD.disc_view_factor(15.0, MD.disc_aperture_for_view_factor(0.9, 15.0, 10.0) / 2, 10.0) == pytest.approx(
        0.9, abs=1e-6)
    # camera: diagonal half-angle of 56 x 42 deg; level set-back (12 - 3) / 2 / tan(diag)
    c = MD.checks()
    assert c["cam_diag_half_deg"] == pytest.approx(33.26, abs=0.02)
    assert c["cam_setback_level"] == pytest.approx(4.5 / math.hypot(math.tan(math.radians(28)),
                                                                     math.tan(math.radians(21))), rel=1e-9)
    assert c["cam_setback_pitched"] < c["cam_setback_level"]
    # radar: 10 + 2 * 13 * tan 60
    assert MD.radar_aperture_mm(13.0, 60.0) == pytest.approx(10 + 26 * math.sqrt(3), rel=1e-12)
    # disc: 0.95 * 20 kW/m2 / (8960 * 385 * 1 mm) K/s
    assert MD.disc_rate_k_s(20.0) == pytest.approx(0.95 * 20000 / (8960 * 385 * 0.001), rel=1e-12)
    h = _read("HOUSING.md")
    for s in ("1.44-1.54 mm", "0.53", "0.44", "66-83 mm", "6.9 mm", "4.4 mm", "-10 to -11 dB", "16-51 K"):
        assert s in h, s


# ------------------------------------------------------------------ (c) README First run
FIRST_RUN_CMDS = (
    "cd ~/wildfireguardian/hardware/vehicle-unit && python3 -m wfgvu.tccheck",
    "cd ~/wildfireguardian/hardware/vehicle-unit && python3 -m wfgvu --sim samples/flame_front --loop --no-record",
    "cd ~/wildfireguardian/hardware/vehicle-unit && python3 -m wfgvu\n",
    "sudo systemctl start wfgvu",
    "cd apps/crossing && ./run_crossing.sh --pi ws://10.42.0.1:8770/stream",
)


def _first_run() -> str:
    r = (VU / "README.md").read_text(encoding="utf-8")
    assert "\n## First run\n" in r
    sec = r.split("\n## First run\n", 1)[1]
    return sec.split("\n## ", 1)[0]


def test_readme_first_run_has_the_four_commands_in_order():
    sec = _first_run()
    pos = []
    for cmd in FIRST_RUN_CMDS:
        assert cmd in sec, cmd
        pos.append(sec.index(cmd))
    assert pos == sorted(pos), "First run commands out of order"
    heads = [sec.index(h) for h in ("### 1. Thermocouple check", "### 2. Simulated mode on the Pi", "### 3. Real mode",
                                    "### 4. Laptop app")]
    assert heads == sorted(heads)
    blocks = re.findall(r"```sh\n(.*?)```", sec, re.S)
    assert len(blocks) >= 5
    for s in ("STOP: flux disc at X C >= 70 C (PETG tabs)", "sudo systemctl stop wfgvu", "| 0 |", "| 1 |", "| 2 |",
              "| 3 |", "spidev0.0", "spidev0.1", "--fake", "--fake-disc-c", "PLATE_DISC_OVER_TEMP",
              "Flux disc over 70 C: PETG tabs at risk", "--replay ../../hardware/vehicle-unit/samples/flame_front"):
        assert s in sec, s
    assert "None of them has been run on the real hardware" in sec


def test_crossing_readme_points_to_first_run():
    t = (CROSSING / "README.md").read_text(encoding="utf-8")
    assert re.search(r"hardware/vehicle-unit/README\.md`?, section \"First run\"", t)


def _help(module: str) -> str:
    out = subprocess.run([sys.executable, "-m", module, "--help"], cwd=str(VU), capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_first_run_modules_and_flags_exist():
    sys.path.insert(0, str(VU))
    try:
        import wfgvu.tccheck as tc  # noqa: F401  (created by the Pi owner; this test fails until it exists)
    finally:
        sys.path.remove(str(VU))
    h = _help("wfgvu.tccheck")
    for flag in ("--config", "--seconds", "--hz", "--fake", "--fake-disc-c"):
        assert flag in h, flag
    for name, code in (("EXIT_OK", 0), ("EXIT_FAULT", 1), ("EXIT_DISC", 2), ("EXIT_ACCESS", 3)):
        if hasattr(tc, name):
            assert getattr(tc, name) == code, name
    h = _help("wfgvu")
    for flag in ("--sim", "--loop", "--no-record"):
        assert flag in h, flag
    assert (VU / "samples" / "flame_front").is_dir()
    run = (CROSSING / "run_crossing.sh").read_text(encoding="utf-8")
    assert "--pi ws://10.42.0.1:8770/stream" in run and "--replay" in run
    main = (CROSSING / "crossing" / "__main__.py").read_text(encoding="utf-8")
    for flag in ('"--pi"', '"--replay"', '"--loop"'):
        assert flag in main, flag
    assert (CROSSING / "../../hardware/vehicle-unit/samples/flame_front").resolve().is_dir()


# ------------------------------------------------------------------ honesty / repo rules
def test_readme_not_verified_and_allowed_claim():
    r = (VU / "README.md").read_text(encoding="utf-8")
    assert "## Not verified on hardware" in r
    assert "2026-11-17" in r
    assert ALLOWED_CLAIM in r
    assert "DESIGN.md" in r
    assert "python -m wfgvu --sim samples/" in r
    for pkg in ("python3-opencv", "python3-spidev", "python3-smbus2", "raspi-config"):
        assert pkg in r, pkg
    assert "InfiRay P2 Pro" in r and "0bda:5830" in r
    for s in ("3V3 pin 17, GND pin 20, CLK pin 23 (GPIO11), DO pin 21 (GPIO9)", "GPIO8, pin 24", "GPIO7, pin 26",
              "GPIO5, pin 29", "3V3 pin 1, GND pin 6, SDA pin 3, SCL pin 5"):
        assert s in r, s


@pytest.mark.parametrize("name", ["WIRING.md", "HOUSING.md", "BOM.md", "MOUNTING_AND_POWER.md"])
def test_docs_have_status_and_no_overclaim(name):
    t = _read(name)
    assert t.startswith("# ")
    assert "2026-11-17" in t
    low = t.lower()
    for m in re.finditer(r"operationally ready|field[- ]proven|works on hardware", low):
        assert "not " in low[max(0, m.start() - 25):m.start()], "claim without negation in %s" % name


def test_readme_no_overclaim():
    low = (VU / "README.md").read_text(encoding="utf-8").lower()
    for m in re.finditer(r"operationally ready|field[- ]proven|works on hardware", low):
        assert "not " in low[max(0, m.start() - 25):m.start()]


def test_bom_prices_left_blank_and_parts_named():
    b = _read("BOM.md")
    assert "Price (fill in)" in b
    assert not re.search(r"[$€£₩¥]\s?\d|\d\s?(USD|EUR|KRW|won)\b", b), "prices must not be invented"
    for part in ("Raspberry Pi", "InfiRay P2 Pro", "0bda:5830", "IWR6843AOPEVM", "MAX31855", "BNO055", "GNSS", "12 V",
                 "flux disc", "supplied", "PETG", "GPIO5"):
        assert part in b, part
    rows = "\n".join(line for line in b.splitlines() if line.startswith("|"))
    for gone in ("Die-cast", "germanium", "Germanium", "pot magnets", "PTFE sheet", "GPIO25", "TC001 to the Pi"):
        assert gone not in rows, gone
    for line in b.splitlines():
        if re.match(r"\|\s*[A-G]\d+\s*\|", line):
            assert line.rstrip().endswith("| |"), line


def test_power_budget_marked_approximate():
    t = _read("MOUNTING_AND_POWER.md")
    assert "approximate" in t.lower() and "must be measured" in t.lower()
    for s in ("~3-6 W", "~12 W", "~0.5-1 W", "~2-3 W", "~0.2 W", "CLOSED", "34 mm above the housing base",
              "InfiRay P2 Pro"):
        assert s in t, s


def test_no_forbidden_folder_names_under_hardware():
    bad = [p for p in HARDWARE.rglob("*") if p.is_dir() and p.name in ("logs", "devices")]
    assert not bad, bad


def test_markdown_links_resolve():
    files = [DOCS / n for n in ("WIRING.md", "HOUSING.md", "BOM.md", "MOUNTING_AND_POWER.md")] + [VU / "README.md"]
    for f in files:
        for target in re.findall(r"\]\(([^)#\s]+)\)", f.read_text(encoding="utf-8")):
            if target.startswith("http"):
                continue
            assert (f.parent / target).exists(), "%s links to missing %s" % (f.name, target)


def test_make_drawings_parses_as_python_311():
    ast.parse(_read("make_drawings.py"), feature_version=(3, 11))
    ast.parse(_read("test_docs.py"), feature_version=(3, 11))


# ------------------------------------------------------------------ Pi install (VU-R7)
# Versions in the Raspberry Pi OS bookworm (arm64) archive. pip in a --system-site-packages venv only skips a
# requirement the apt package already satisfies; a minimum above these makes pip build spidev from its sdist, which
# fails without Python.h and aborts the whole install (websockets never installed, service crash-loops).
BOOKWORM_APT = {"numpy": "1.24.2", "pyyaml": "6.0", "pyserial": "3.5", "spidev": "3.5", "smbus2": "0.4.2"}
APT_LIST = ("python3-venv", "python3-numpy", "python3-yaml", "python3-serial", "python3-opencv", "python3-spidev",
            "python3-smbus2", "python3-lgpio", "v4l-utils", "i2c-tools")


def _vtuple(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def test_requirements_pi_minimums_are_met_by_bookworm_apt():
    reqs = {}
    for line in (VU / "requirements-pi.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"([A-Za-z0-9_.-]+)\s*(.*)$", line)
        reqs[m.group(1).lower()] = m.group(2)
    assert reqs.get("websockets") == "==13.1"
    for pkg, apt_v in BOOKWORM_APT.items():
        spec = reqs.get(pkg)
        if spec is None:  # left to apt entirely: fine
            continue
        for op, v in re.findall(r"(>=|==|<=|<|>)\s*([0-9][0-9.]*)", spec):
            if op == ">=":
                assert _vtuple(apt_v) >= _vtuple(v), "%s %s not met by bookworm apt %s" % (pkg, spec, apt_v)
            elif op == "==":
                assert _vtuple(apt_v) == _vtuple(v), "%s %s not met by bookworm apt %s" % (pkg, spec, apt_v)
            elif op == "<":
                assert _vtuple(apt_v) < _vtuple(v), "%s %s not met by bookworm apt %s" % (pkg, spec, apt_v)


@pytest.mark.parametrize("path", ["README.md", "system/README.md", "requirements-pi.txt"])
def test_pi_install_instructions_use_the_same_apt_list(path):
    t = (VU / path).read_text(encoding="utf-8")
    for pkg in APT_LIST:
        assert pkg in t, "%s missing from %s" % (pkg, path)
    assert "--only-binary=:all:" in t, path
