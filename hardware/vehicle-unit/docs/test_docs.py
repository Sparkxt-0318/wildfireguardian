"""Consistency tests for hardware/vehicle-unit/docs and README.md (no hardware, no network, deterministic).

Run:  cd hardware/vehicle-unit && <venv>/bin/python -m pytest docs/test_docs.py

What is checked: the committed SVGs equal what make_drawings.py generates; both SVGs are well-formed with a
title/description; the WIRING.md pin table equals the pin list the drawing is generated from; that pin list and
WIRING.md agree with config/unit.yaml (SPI buses/devices, I2C bus/address, radar baud rates); housing.scad
parameters equal make_drawings.HOUSING; the radome numbers in HOUSING.md follow lambda/(2 sqrt(eps_r)); the README
keeps the 'Not verified on hardware' section and the single allowed claim; BOM prices are left blank; no folder
under hardware/ is named 'logs' or 'devices'. What is NOT checked: anything physical. These are documents.
"""
from __future__ import annotations

import ast
import importlib.util
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parent
VU = DOCS.parent
HARDWARE = VU.parent
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


# ------------------------------------------------------------------ drawings
def test_svgs_are_up_to_date():
    for name, text in MD.outputs().items():
        assert (DOCS / name).read_text(encoding="utf-8") == text, "%s is stale: run docs/make_drawings.py" % name


def test_generation_is_deterministic():
    assert MD.outputs() == MD.outputs()


@pytest.mark.parametrize("name", ["wiring.svg", "housing.svg"])
def test_svg_well_formed_and_accessible(name):
    root = ET.parse(DOCS / name).getroot()
    assert root.tag == SVG_NS + "svg"
    assert root.get("viewBox") and root.get("role") == "img"
    assert root.find(SVG_NS + "title").text.strip()
    assert len(root.find(SVG_NS + "desc").text) > 40
    w, h = (float(v) for v in root.get("viewBox").split()[2:])
    # every coordinate stays on the canvas (legibility: nothing drawn off-page)
    for el in root.iter():
        for attr in ("x", "x1", "x2", "cx"):
            if el.get(attr) is not None:
                assert -1 <= float(el.get(attr)) <= w + 1, (name, el.tag, attr, el.get(attr))
        for attr in ("y", "y1", "y2", "cy"):
            if el.get(attr) is not None:
                assert -1 <= float(el.get(attr)) <= h + 1, (name, el.tag, attr, el.get(attr))
        if el.tag == SVG_NS + "text":
            assert float(el.get("font-size")) >= 9.5, "text too small to read"


def _svg_text(name: str) -> str:
    root = ET.parse(DOCS / name).getroot()
    return "\n".join((t.text or "") for t in root.iter(SVG_NS + "text"))


def test_wiring_svg_labels_every_used_pin_and_net():
    txt = _svg_text("wiring.svg")
    for pin, (net, label) in MD.USED_PINS.items():
        assert re.search(r"(^|\n)%d(\n|$)" % pin, txt), "pin number %d not labelled" % pin
        assert label in txt
        assert MD.NETS[net][2] in txt or net in ("V12", "V5"), "legend lacks %s" % net
    for must in ("0x28", "i2c_arm_baudrate=10000", "115200", "921600", "5 A blade fuse", "TVS",
                 "+ yellow", "- red", "spi1-1cs", "no_cs"):
        assert must in txt, must


def test_housing_svg_has_dimensions_and_views():
    txt = _svg_text("housing.svg")
    for must in ("FRONT VIEW", "SIDE VIEW", "TOP VIEW", "%d" % MD.HOUSING["box_w"], "%d" % MD.HOUSING["box_l"],
                 "%d" % MD.HOUSING["box_h"], "plate %d" % MD.HOUSING["plate_a"], "%d proud" % MD.HOUSING["plate_proud"],
                 "PTFE radome", "Ge", "1.47 mm", "1.72 mm", "opaque in LWIR"):
        assert must in txt, must


# ------------------------------------------------------------------ wiring table vs drawing vs unit.yaml
def _wiring_pin_rows():
    rows = {}
    for line in _read("WIRING.md").splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([A-Z0-9_]+)\s*\|", line)
        if m:
            rows[int(m.group(1))] = (m.group(2), m.group(3))
    return rows


def test_wiring_md_pin_table_matches_drawing():
    rows = _wiring_pin_rows()
    assert set(rows) == set(MD.USED_PINS), (sorted(rows), sorted(MD.USED_PINS))
    for pin, (signal, net) in rows.items():
        assert net == MD.USED_PINS[pin][0], (pin, net)
        # the signal column must agree with the physical pin name used in the drawing
        assert MD.PI_PINS[pin].split()[0] in signal, (pin, signal, MD.PI_PINS[pin])


def test_header_pinout_constants():
    # fixed Raspberry Pi J8 facts the whole page relies on
    assert MD.PI_PINS[19].startswith("GPIO10") and MD.PI_PINS[21].startswith("GPIO9")
    assert MD.PI_PINS[23].startswith("GPIO11") and MD.PI_PINS[24].startswith("GPIO8")
    assert MD.PI_PINS[26].startswith("GPIO7") and MD.PI_PINS[22] == "GPIO25"
    assert MD.PI_PINS[3].startswith("GPIO2") and MD.PI_PINS[5].startswith("GPIO3")
    assert MD.PI_PINS[12].startswith("GPIO18") and MD.PI_PINS[35].startswith("GPIO19")
    assert MD.PI_PINS[40].startswith("GPIO21")
    assert sum(1 for v in MD.PI_PINS.values() if v == "GND") == 8
    assert len(MD.PI_PINS) == 40


# spi (bus, dev) -> header pins of (CS, SCLK, MISO)
SPI_PINS = {(0, 0): (24, 23, 21), (0, 1): (26, 23, 21), (1, 0): (12, 40, 35)}
CS_NET = {"tc_plate": "CS_PLATE", "tc_housing": "CS_HOUSING", "tc_air": "CS_AIR"}


def _unit_yaml():
    yaml = pytest.importorskip("yaml")
    p = VU / "config" / "unit.yaml"
    if not p.is_file():
        pytest.skip("config/unit.yaml not present; WIRING.md section 8 states the defaults")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_unit_yaml_spi_matches_wiring():
    cfg = _unit_yaml()["sensors"]
    for name, net in CS_NET.items():
        bus, dev = int(cfg[name]["spi_bus"]), int(cfg[name]["spi_dev"])
        assert (bus, dev) in SPI_PINS, "%s on spi%d.%d is not a wiring this page documents" % (name, bus, dev)
        cs, sclk, miso = SPI_PINS[(bus, dev)]
        assert MD.USED_PINS[cs][0] == net, "%s CS should be on pin %d" % (name, cs)
        assert MD.USED_PINS[sclk][0].startswith("SCLK") and MD.USED_PINS[miso][0].startswith("MISO")
        row = "| `%s` | `spi_bus`, `spi_dev` | %d, %d |" % (name, bus, dev)
        assert row in _read("WIRING.md"), "WIRING.md section 8 lacks: " + row
    assert "cs_gpio" not in cfg["tc_air"], "software CS configured: update WIRING.md default and the drawing"


def test_unit_yaml_i2c_and_radar_match_wiring():
    cfg = _unit_yaml()["sensors"]
    assert int(cfg["imu"]["i2c_bus"]) == 1 and int(cfg["imu"]["address"]) == 0x28
    assert int(cfg["radar"]["cli_baud"]) == 115200 and int(cfg["radar"]["data_baud"]) == 921600
    w = _read("WIRING.md")
    assert "| `imu` | `i2c_bus`, `address` | 1, 0x28 |" in w


# ------------------------------------------------------------------ housing model
def _scad_params():
    out = {}
    for line in _read("housing.scad").splitlines():
        m = re.match(r"^([a-z_0-9]+)\s*=\s*(-?[0-9.]+)\s*;", line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def test_scad_parameters_match_drawing():
    p = _scad_params()
    for k, v in MD.HOUSING.items():
        assert k in p, "housing.scad lacks parameter %s" % k
        assert p[k] == pytest.approx(float(v)), (k, p[k], v)


def test_scad_brackets_balanced():
    src = _read("housing.scad")
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r'"[^"\n]*"', '""', src)
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for i, ch in enumerate(src):
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            assert stack and stack[-1] == pairs[ch], "unbalanced %r at offset %d" % (ch, i)
            stack.pop()
    assert not stack
    for mod in ("enclosure", "radome", "ir_window", "base_plate", "magnets", "shield", "plate_bracket", "assembly"):
        assert re.search(r"module %s\s*\(" % mod, src), mod


def test_radome_thickness_formula():
    assert MD.radome_thickness_mm(2.9) == pytest.approx(1.467, abs=0.002)
    assert MD.radome_thickness_mm(2.1) == pytest.approx(1.724, abs=0.002)
    assert MD.radome_thickness_mm(2.1, n=2) == pytest.approx(3.448, abs=0.002)
    lam = 299_792_458.0 / 60e9 * 1000.0
    assert lam == pytest.approx(4.997, abs=0.001)
    h = _read("HOUSING.md")
    for s in ("1.47 mm", "1.72 mm", "3.45 mm", "lambda0 / (2 * sqrt(eps_r))"):
        assert s in h, s
    assert math.isclose(MD.derived(MD.HOUSING)["radome_t"], MD.radome_thickness_mm(2.1, n=2))


def test_housing_overall_height_stated_consistently():
    d = MD.derived(MD.HOUSING)
    assert round(d["z_sh1"]) == 131
    assert "131 mm above the roof skin" in _read("HOUSING.md")


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


def test_bom_prices_left_blank():
    b = _read("BOM.md")
    assert "Price (fill in)" in b
    assert not re.search(r"[$€£₩¥]\s?\d|\d\s?(USD|EUR|KRW|won)\b", b), "prices must not be invented"
    for part in ("Raspberry Pi", "TC001", "IWR6843AOPEVM", "MAX31855", "BNO055", "GNSS", "12 V", "flux plate"):
        assert part in b, part
    # every table row in the BOM ends with an empty price cell
    for line in b.splitlines():
        if re.match(r"\|\s*[A-G]\d+\s*\|", line):
            assert line.rstrip().endswith("| |"), line


def test_power_budget_marked_approximate():
    t = _read("MOUNTING_AND_POWER.md")
    assert "approximate" in t.lower() and "must be measured" in t.lower()
    for s in ("~3-6 W", "~12 W", "~0.5-1 W", "~2-3 W", "~0.2 W", "CLOSED"):
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
