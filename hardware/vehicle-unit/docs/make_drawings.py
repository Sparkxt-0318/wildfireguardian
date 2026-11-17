"""Generate docs/wiring.svg and docs/housing.svg for the WildfireGuardian vehicle unit.

Stdlib only, Python 3.11+. Run from anywhere:

    python hardware/vehicle-unit/docs/make_drawings.py          # rewrite both SVGs
    python hardware/vehicle-unit/docs/make_drawings.py --check  # exit 1 if the committed SVGs differ

The drawings are concept drawings, not a verified build. Every dimension is in millimetres and is a design
value: nothing here has been fabricated or measured (status 2026-11-17). The housing dimensions in ``HOUSING``
are mirrored by the top-level parameters of ``housing.scad``; ``docs/test_docs.py`` checks that they agree.

Vehicle axes used for the housing (ISO 8855 style): X forward, Y to the vehicle's left, Z up; origin at the
centre of the enclosure footprint on the car roof (Z = 0 is the roof skin under the magnets).

Radome physics (stated, not measured): a dielectric slab is transparent at normal incidence when its electrical
thickness is a whole number of half wavelengths, t_n = n * lambda0 / (2 * sqrt(eps_r)). With lambda0 = c / f,
f = 60 GHz: polycarbonate eps_r ~ 2.9 gives t_1 ~ 1.47 mm, PTFE eps_r ~ 2.1 gives t_1 ~ 1.72 mm. The IWR6843 stock
demo chirps span roughly 60-64 GHz, so the slab is only exactly matched at one frequency in the band.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
C0 = 299_792_458.0  # speed of light, m/s


def radome_thickness_mm(eps_r: float, f_hz: float = 60e9, n: int = 1) -> float:
    """Half-wave-multiple radome thickness in mm: n * lambda0 / (2 * sqrt(eps_r)), normal incidence."""
    lam_mm = C0 / f_hz * 1000.0
    return n * lam_mm / (2.0 * math.sqrt(eps_r))


# --------------------------------------------------------------------------------------------------------------
# Housing design values (mm). Mirrored in housing.scad; keep the names identical.
# --------------------------------------------------------------------------------------------------------------
HOUSING = {
    "box_l": 160.0,          # enclosure length along X (forward), external
    "box_w": 220.0,          # enclosure width along Y, external
    "box_h": 90.0,           # enclosure height along Z, external
    "wall": 3.0,             # die-cast aluminium wall
    "base_l": 240.0,         # aluminium base plate along X
    "base_w": 320.0,         # base plate along Y
    "base_t": 5.0,           # base plate thickness
    "magnet_d": 88.0,        # rubber-coated pot magnet diameter
    "magnet_h": 15.0,        # magnet height incl. rubber boot
    "radome_w": 60.0,        # radar window (Y) on the front face
    "radome_h": 60.0,        # radar window (Z)
    "radome_y": -45.0,       # window centre Y (negative = vehicle right)
    "radome_z": 45.0,        # window centre height above enclosure bottom
    "radome_eps_r": 2.1,     # PTFE (polycarbonate would be 2.9)
    "radome_n": 2,           # number of half wavelengths (2 -> stiffer, see HOUSING.md)
    "ir_win_d": 25.0,        # germanium LWIR window diameter
    "ir_win_t": 2.0,         # germanium window thickness
    "ir_win_y": 35.0,        # LWIR window centre Y (vehicle left of centre)
    "ir_win_z": 55.0,        # LWIR window centre height above enclosure bottom
    "plate_a": 50.0,         # copper flux plate edge
    "plate_t": 1.0,          # copper flux plate thickness
    "board_a": 70.0,         # ceramic fibre board backing edge
    "board_t": 25.0,         # ceramic fibre board thickness
    "plate_proud": 40.0,     # plate front face ahead of the enclosure front face (X)
    "plate_y": 155.0,        # plate centre Y (vehicle left, outboard of the enclosure)
    "plate_z": 50.0,         # plate centre height above enclosure bottom
    "shield_gap": 20.0,      # air gap between lid and sun/heat shield
    "shield_t": 1.0,         # shield sheet thickness
    "shield_over": 20.0,     # shield overhang beyond the enclosure on every side
    "gland_d": 16.0,         # M16 cable gland thread diameter (rear face)
    "rf_win_w": 80.0,        # rear polycarbonate RF window (Wi-Fi) width, Y
    "rf_win_h": 30.0,        # rear RF window height, Z
}

GLAND_Y = (-75.0, -25.0, 25.0, 75.0)   # rear-face gland centres (Y), at height GLAND_Z above enclosure bottom
GLAND_Z = 25.0
VENT_Y = 95.0                          # membrane vent (M12) centre Y on the rear face


def derived(h: dict) -> dict:
    """Heights and extents derived from HOUSING (mm, vehicle axes)."""
    d = {}
    d["z_base0"] = h["magnet_h"]
    d["z_box0"] = h["magnet_h"] + h["base_t"]
    d["z_box1"] = d["z_box0"] + h["box_h"]
    d["z_sh0"] = d["z_box1"] + h["shield_gap"]
    d["z_sh1"] = d["z_sh0"] + h["shield_t"]
    d["x_front"] = h["box_l"] / 2
    d["x_plate"] = d["x_front"] + h["plate_proud"]
    d["radome_t"] = radome_thickness_mm(h["radome_eps_r"], 60e9, int(h["radome_n"]))
    return d


# --------------------------------------------------------------------------------------------------------------
# Minimal SVG helpers
# --------------------------------------------------------------------------------------------------------------
def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def f(v: float) -> str:
    """Compact, deterministic number formatting for SVG coordinates."""
    r = round(v, 2)
    if r == int(r):
        return str(int(r))
    return ("%.2f" % r).rstrip("0").rstrip(".")


class Svg:
    def __init__(self, w: int, h: int, title: str, desc: str):
        self.w, self.h = w, h
        self.parts: list[str] = []
        self.title, self.desc = title, desc

    def add(self, s: str) -> None:
        self.parts.append(s)

    def line(self, x1, y1, x2, y2, stroke="#222", width=2.0, dash=None, cls=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        c = ' class="%s"' % cls if cls else ""
        self.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"%s%s/>'
                 % (f(x1), f(y1), f(x2), f(y2), stroke, f(width), d, c))

    def poly(self, pts, stroke="#222", width=2.0, dash=None, fill="none"):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        p = " ".join("%s,%s" % (f(x), f(y)) for x, y in pts)
        self.add('<polyline points="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"%s/>'
                 % (p, fill, stroke, f(width), d))

    def rect(self, x, y, w, h, fill="#fff", stroke="#222", width=1.5, rx=0, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.add('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" stroke-width="%s"%s/>'
                 % (f(x), f(y), f(w), f(h), f(rx), fill, stroke, f(width), d))

    def circle(self, cx, cy, r, fill="#fff", stroke="#222", width=1.5, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.add('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="%s"%s/>'
                 % (f(cx), f(cy), f(r), fill, stroke, f(width), d))

    def text(self, x, y, s, size=12, anchor="start", weight="normal", fill="#111", italic=False):
        st = ' font-style="italic"' if italic else ""
        self.add('<text x="%s" y="%s" font-size="%s" text-anchor="%s" font-weight="%s" fill="%s"%s>%s</text>'
                 % (f(x), f(y), f(size), anchor, weight, fill, st, esc(s)))

    def lines(self, x, y, rows, size=12, step=None, **kw):
        step = step or size * 1.3
        for i, r in enumerate(rows):
            self.text(x, y + i * step, r, size=size, **kw)

    def dot(self, x, y, color="#222"):
        self.circle(x, y, 3.5, fill=color, stroke=color, width=1)

    def render(self) -> str:
        head = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
                'role="img" aria-labelledby="t d" font-family="Helvetica, Arial, sans-serif">\n'
                '<title id="t">%s</title>\n<desc id="d">%s</desc>\n'
                '<defs><marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" '
                'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>\n'
                '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>\n'
                % (self.w, self.h, self.w, self.h, esc(self.title), esc(self.desc), self.w, self.h))
        return head + "\n".join(self.parts) + "\n</svg>\n"


# --------------------------------------------------------------------------------------------------------------
# Wiring diagram
# --------------------------------------------------------------------------------------------------------------
PI_PINS = {
    1: "3V3", 2: "5V", 3: "GPIO2 SDA1", 4: "5V", 5: "GPIO3 SCL1", 6: "GND", 7: "GPIO4", 8: "GPIO14 TXD",
    9: "GND", 10: "GPIO15 RXD", 11: "GPIO17", 12: "GPIO18 SPI1 CE0", 13: "GPIO27", 14: "GND", 15: "GPIO22",
    16: "GPIO23", 17: "3V3", 18: "GPIO24", 19: "GPIO10 MOSI", 20: "GND", 21: "GPIO9 MISO", 22: "GPIO25",
    23: "GPIO11 SCLK", 24: "GPIO8 CE0", 25: "GND", 26: "GPIO7 CE1", 27: "ID_SD", 28: "ID_SC", 29: "GPIO5",
    30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND", 35: "GPIO19 SPI1 MISO", 36: "GPIO16", 37: "GPIO26",
    38: "GPIO20", 39: "GND", 40: "GPIO21 SPI1 SCLK",
}

# Net colours. Every wire also carries a text label, so colour is never the only cue (accessibility).
NETS = {
    "3V3": ("#d62728", None, "3V3 (red)"),
    "GND": ("#222222", None, "GND (black)"),
    "SCLK": ("#ff7f0e", None, "SPI0 SCLK (orange)"),
    "MISO": ("#2ca02c", None, "SPI0 MISO (green)"),
    "SCLK1": ("#ff7f0e", "12 3 3 3", "SPI1 SCLK (orange, dash-dot)"),
    "MISO1": ("#2ca02c", "12 3 3 3", "SPI1 MISO (green, dash-dot)"),
    "CS_PLATE": ("#1f77b4", "8 4", "CS plate, CE0 (blue, dashed)"),
    "CS_HOUSING": ("#9467bd", "8 4", "CS housing, CE1 (purple, dashed)"),
    "CS_AIR": ("#8c564b", "8 4", "CS air, SPI1 CE0 (brown, dashed)"),
    "SDA": ("#17becf", "2 3", "I2C1 SDA (cyan, dotted)"),
    "SCL": ("#e377c2", "2 3", "I2C1 SCL (pink, dotted)"),
    "TCP": ("#c9a400", None, "Type-K + (yellow, ANSI)"),
    "TCN": ("#d62728", "6 3", "Type-K - (red, ANSI, dashed here)"),
    "V12": ("#d62728", None, "+12 V"),
    "V5": ("#ff7f0e", None, "+5 V"),
    "USB": ("#555555", "10 3 2 3", "USB cable (grey, dash-dot)"),
}

# Header pin -> (net, label on the wire). Matches config/unit.yaml (tc_plate SPI0 CE0, tc_housing SPI0 CE1,
# tc_air SPI1 CE0, imu I2C1 0x28). test_docs.py checks this against the WIRING.md pin table and unit.yaml.
USED_PINS = {
    1: ("3V3", "MAX31855 VIN x3"),
    3: ("SDA", "BNO055 SDA"),
    5: ("SCL", "BNO055 SCL"),
    9: ("GND", "BNO055 GND"),
    12: ("CS_AIR", "air CS"),
    17: ("3V3", "BNO055 VIN"),
    20: ("GND", "MAX31855 GND x3"),
    21: ("MISO", "plate+housing DO"),
    23: ("SCLK", "plate+housing CLK"),
    24: ("CS_PLATE", "plate CS"),
    26: ("CS_HOUSING", "housing CS"),
    35: ("MISO1", "air DO"),
    40: ("SCLK1", "air CLK"),
}


def wiring_svg() -> str:
    W, H = 1400, 1130
    s = Svg(W, H, "WildfireGuardian vehicle unit wiring",
            "Raspberry Pi 4/5 40-pin header with three MAX31855 thermocouple amplifiers (SPI0 CE0 plate, "
            "SPI0 CE1 housing, SPI1 CE0 air), BNO055 on I2C1 at 0x28, USB thermal camera, radar "
            "EVM and GNSS, and the fused 12 V to 5 V power chain. Design drawing, not verified on hardware.")
    s.text(30, 38, "WildfireGuardian vehicle unit: wiring (Raspberry Pi 4 / 5)", size=22, weight="bold")
    s.text(30, 62, "Design defaults from DESIGN.md and config/unit.yaml. Not built or verified on hardware as of "
                   "2026-11-17. Header viewed from above, pin 1 top left (SD-card end away from you).",
           size=13, fill="#444")

    # Header
    Y0, S = 150, 26
    hx0, hx1 = 540, 720
    xo, xe = 605, 655
    s.rect(hx0, Y0 - 24, hx1 - hx0, 20 * S + 22, fill="#f4f4f4", stroke="#333", width=2, rx=6)
    s.text((hx0 + hx1) / 2, Y0 - 32, "Raspberry Pi 40-pin header (J8)", size=14, anchor="middle", weight="bold")

    def py(pin: int) -> float:
        return Y0 + ((pin - 1) // 2) * S

    for pin, name in PI_PINS.items():
        odd = pin % 2 == 1
        x = xo if odd else xe
        used = pin in USED_PINS
        col = NETS[USED_PINS[pin][0]][0] if used else "#bbb"
        s.circle(x, py(pin), 7, fill=col if used else "#fff", stroke="#333" if used else "#999", width=1.2)
        s.text(x - 20 if odd else x + 20, py(pin) + 4, str(pin), size=11,
               anchor="end" if odd else "start", weight="bold" if used else "normal",
               fill="#111" if used else "#888")
        if used:
            net, lab = USED_PINS[pin]
            colr, dash, _ = NETS[net]
            xend = 420 if odd else 860
            s.line(hx0 if odd else hx1, py(pin), xend, py(pin), stroke=colr, width=2.5, dash=dash)
            s.text(hx0 - 8 if odd else hx1 + 8, py(pin) - 5, "%s <- %s" % (lab, name) if odd else
                   "%s -> %s" % (name, lab), size=10.5, anchor="end" if odd else "start", fill="#111")
        else:
            s.text(hx0 - 8 if odd else hx1 + 8, py(pin) + 4, name, size=10, anchor="end" if odd else "start",
                   fill="#999")

    # ---------------- MAX31855 boards (right) ----------------
    bx0, bx1 = 1010, 1150
    boards = [("plate", "MAX31855 #1  tc_plate  (SPI0 CE0)", 120, "CS_PLATE", 990,
               ["Copper flux plate 50x50x1 mm", "junction peened into the plate,", "plate isolated from chassis"]),
              ("housing", "MAX31855 #2  tc_housing  (SPI0 CE1)", 290, "CS_HOUSING", 975,
               ["Housing interior", "K probe taped to the wall", "away from Pi and buck"]),
              ("air", "MAX31855 #3  tc_air  (SPI1 CE0)", 460, "CS_AIR", 960,
               ["Intake-height air probe", "radiation-shielded, ungrounded", "separate type-K extension lead"])]
    bus = {"3V3": 880, "GND": 900, "MISO": 920, "SCLK": 940}
    spi0_last_top = boards[1][2]
    pin_off = {"VIN": 25, "GND": 45, "DO": 65, "CS": 85, "CLK": 105}
    first_top = boards[0][2]
    last_top = boards[-1][2]
    # 3V3 from pin 1: left, up over the header, right to the bus
    c3 = NETS["3V3"][0]
    s.poly([(420, py(1)), (420, 100), (bus["3V3"], 100), (bus["3V3"], last_top + pin_off["VIN"])],
           stroke=c3, width=2.5)
    s.text(470, 95, "3V3 from pin 1 to MAX31855 VIN (3.0-3.6 V part: never 5 V)", size=10.5, fill=c3)
    # GND from pin 20
    cg = NETS["GND"][0]
    s.poly([(860, py(20)), (bus["GND"], py(20))], stroke=cg, width=2.5)
    s.line(bus["GND"], first_top + pin_off["GND"], bus["GND"], last_top + pin_off["GND"], stroke=cg, width=2.5)
    s.dot(bus["GND"], py(20), cg)
    # MISO and SCLK from pins 21 / 23: left, down under the header, right, up
    yb = {"MISO": 700, "SCLK": 718}
    for net, pin, xl in (("MISO", 21, 360), ("SCLK", 23, 375)):
        colr = NETS[net][0]
        s.poly([(420, py(pin)), (xl, py(pin))], stroke=colr, width=2.5)
        s.poly([(xl, py(pin)), (xl, yb[net]), (bus[net], yb[net]), (bus[net], first_top + pin_off[
            "DO" if net == "MISO" else "CLK"])], stroke=colr, width=2.5)
        s.text(1010, yb[net] + 4, "SPI0 %s (pin %d): plate + housing boards only" % (net, pin), size=10.5,
               fill=colr)
    # SPI1 for the air board: MISO1 from pin 35 (left side, under the header), SCLK1 from pin 40 (right side)
    air_top = boards[2][2]
    c_m1, d_m1, _ = NETS["MISO1"]
    s.poly([(420, py(35)), (345, py(35)), (345, 738), (1000, 738), (1000, air_top + pin_off["DO"]),
            (bx0, air_top + pin_off["DO"])], stroke=c_m1, width=2.5, dash=d_m1)
    s.text(1010, 742, "SPI1 MISO (pin 35): air board only", size=10.5, fill=c_m1)
    c_s1, d_s1, _ = NETS["SCLK1"]
    s.poly([(860, py(40)), (970, py(40)), (970, air_top + pin_off["CLK"]), (bx0, air_top + pin_off["CLK"])],
           stroke=c_s1, width=2.5, dash=d_s1)
    for key, title, top, csnet, xcs, sensor in boards:
        s.rect(bx0, top, bx1 - bx0, 125, fill="#eef5ff", stroke="#1f3b66", width=1.8, rx=5)
        s.text(bx0, top - 6, title, size=12.5, weight="bold")
        for pn, off in pin_off.items():
            y = top + off
            s.text(bx0 + 8, y + 4, pn, size=10.5)
            net = {"VIN": "3V3", "GND": "GND", "DO": "MISO", "CLK": "SCLK"}.get(pn)
            if net in ("MISO", "SCLK") and key == "air":
                net = None       # the air board is on SPI1, drawn separately above
            if net:
                colr, dash, _ = NETS[net]
                s.line(bus[net], y, bx0, y, stroke=colr, width=2.5, dash=dash)
                s.dot(bus[net], y, colr)
        # CS
        colr, dash, _ = NETS[csnet]
        src_pin = {"CS_PLATE": 24, "CS_HOUSING": 26, "CS_AIR": 12}[csnet]
        s.poly([(860, py(src_pin)), (xcs, py(src_pin)), (xcs, top + pin_off["CS"]), (bx0, top + pin_off["CS"])],
               stroke=colr, width=2.5, dash=dash)
        # thermocouple side
        s.text(bx1 - 8, top + 50, "T+", size=10.5, anchor="end")
        s.text(bx1 - 8, top + 80, "T-", size=10.5, anchor="end")
        s.line(bx1, top + 46, 1215, top + 46, stroke=NETS["TCP"][0], width=3)
        s.line(bx1, top + 76, 1215, top + 76, stroke=NETS["TCN"][0], width=3, dash=NETS["TCN"][1])
        s.text(1157, top + 41, "+ yellow", size=9.5, fill="#7a6400")
        s.text(1157, top + 92, "- red", size=9.5, fill="#a01010")
        s.rect(1215, top + 22, 175, 80, fill="#fffbe6", stroke="#8a7300", width=1.4, rx=4)
        s.lines(1222, top + 40, sensor, size=10.5, step=15)
        s.text(1222, top + 95, "type-K wire end to end", size=9.5, fill="#7a6400", italic=True)
    s.lines(bx0 - 4, 600, ["All chip selects are kernel CS, active low: plate spidev0.0, housing",
                           "spidev0.1, air spidev1.0 (dtoverlay=spi1-1cs). No software CS needed.",
                           "Alternative (not default): air CS on GPIO25 pin 22 as a SOFTWARE CS",
                           "on SPI0, needs spidev no_cs + lgpio in the driver (not implemented).",
                           "10 nF across T+/T- at each MAX31855. MOSI pins unused (read-only)."],
            size=10.5, step=15)

    # ---------------- BNO055 (left) ----------------
    cx0, cx1 = 150, 300
    s.rect(cx0, 150, cx1 - cx0, 305, fill="#f0fff4", stroke="#1d5e33", width=1.8, rx=5)
    s.text((cx0 + cx1) / 2, 143, "BNO055 IMU breakout  (imu)", size=12.5, anchor="middle", weight="bold")
    for pn, pin in (("SDA", 3), ("SCL", 5), ("GND", 9), ("VIN", 17)):
        net = USED_PINS[pin][0]
        colr, dash, _ = NETS[net]
        y = py(pin)
        s.line(420, y, cx1, y, stroke=colr, width=2.5, dash=dash)
        s.text(cx1 - 8, y + 4, pn, size=10.5, anchor="end")
    s.lines(cx0 + 8, 382, ["ADR -> GND: address 0x28", "PS0, PS1 -> GND: I2C mode", "I2C1 (bus 1)",
                           "BNO055 stretches SCL; Pi I2C", "mishandles it: set"], size=10, step=13)
    s.text(cx0 + 8, 447, "i2c_arm_baudrate=10000", size=10, weight="bold")
    s.lines(30, 478, ["UART alternative (not the default): PS1 -> 3V3,",
                      "BNO055 TX -> GPIO15 RXD (pin 10), RX -> GPIO14 TXD",
                      "(pin 8), 115200 baud, enable_uart=1, serial console off."], size=10.5, step=15)

    # ---------------- USB devices (bottom left) ----------------
    uy = 830
    s.text(30, uy - 20, "USB devices (Pi USB-A ports)", size=15, weight="bold")
    s.rect(30, uy, 150, 200, fill="#f4f4f4", stroke="#333", width=1.8, rx=5)
    s.lines(40, uy + 25, ["Raspberry Pi", "USB 3.0 x2 (blue)", "USB 2.0 x2", "", "Pi 4: 1.2 A total",
                          "Pi 5: 600 mA total", "unless 5 V 5 A PD", "(or usb_max_current", "_enable=1)"],
            size=10.5, step=15)
    cu, du, _ = NETS["USB"]
    devs = [(uy + 10, "Topdon TC001 thermal camera (thermal)",
             ["USB-C plug -> USB-C(f) to USB-A(m) OTG adapter or cable", "UVC 256x384 YUYV, about 0.5-1 W"]),
            (uy + 75, "TI IWR6843AOPEVM radar (radar), stock mmw demo",
             ["micro-USB, 5 V from USB (about 2-3 W). Two serial ports enumerate:",
              "CLI 115200 baud (config) + DATA 921600 baud (TLV frames).",
              "Board must be in functional mode (SOP switch), see WIRING.md."]),
            (uy + 155, "USB GNSS receiver (gnss)",
             ["NMEA over USB serial, about 0.2 W; antenna needs sky view", "(outside the aluminium box)"])]
    for y, title, rows in devs:
        s.line(180, y + 20, 260, y + 20, stroke=cu, width=2.5, dash=du)
        s.rect(260, y, 420, 18 + 15 * len(rows) + 8, fill="#fafafa", stroke="#555", width=1.3, rx=4)
        s.text(268, y + 15, title, size=11.5, weight="bold")
        s.lines(268, y + 31, rows, size=10.5, step=15)
    s.text(190, uy + 225, "Option: powered USB hub fed from the 5 V buck if the Pi limits USB current.",
           size=10.5, fill="#444", italic=True)

    # ---------------- Power chain (bottom right) ----------------
    px = 730
    s.text(px, uy - 20, "Power: 12 V accessory socket to Pi", size=15, weight="bold")
    blocks = [("12 V socket", ["vehicle accessory", "plug (own fuse)"]),
              ("5 A blade fuse", ["inline, close", "to the plug"]),
              ("Reverse polarity", ["ideal diode /", "P-FET (or Schottky)"]),
              ("TVS to GND", ["load-dump clamp,", "unidirectional"]),
              ("12 -> 5 V buck", ["automotive, 5 V 5 A,", "input >= 36 V rated"])]
    bw, gap = 112, 14
    c12 = NETS["V12"][0]
    for i, (t, rows) in enumerate(blocks):
        x = px + i * (bw + gap)
        s.rect(x, uy, bw, 70, fill="#fff5f5", stroke="#7a1010", width=1.5, rx=4)
        s.text(x + bw / 2, uy + 18, t, size=11.5, anchor="middle", weight="bold")
        s.lines(x + bw / 2, uy + 36, rows, size=10, step=14, anchor="middle")
        if i < len(blocks) - 1:
            s.line(x + bw, uy + 35, x + bw + gap, uy + 35, stroke=c12, width=3)
    s.text(px + 10, uy + 90, "+12 V nominal (9-16 V running; dips to about 6 V while cranking; transients above "
                             "24 V possible)", size=10.5, fill=c12)
    # 5 V out to Pi
    c5 = NETS["V5"][0]
    xb = px + 4 * (bw + gap) + bw / 2
    s.poly([(xb, uy + 70), (xb, uy + 120), (px + 60, uy + 120), (px + 60, uy + 140)], stroke=c5, width=3)
    s.rect(px, uy + 140, 300, 60, fill="#fffaf0", stroke="#a35400", width=1.5, rx=4)
    s.lines(px + 10, uy + 158, ["Pi 5: USB-C PD 5.1 V 5 A (27 W class)", "Pi 4: USB-C 5.1 V 3 A",
                                "do not back-feed 5 V via GPIO pins 2/4 unprotected"], size=10.5, step=15)
    s.text(xb - 50, uy + 115, "+5 V", size=10.5, fill=c5, weight="bold")
    s.line(px, uy + 225, px + 640, uy + 225, stroke=cg, width=3)
    s.text(px + 4, uy + 243, "GND / 0 V: returns through the socket plug only. Copper plate and thermocouple "
                             "sheaths stay isolated from chassis.", size=10.5)
    s.text(px + 4, uy + 258, "(a grounded junction makes the MAX31855 report SHORT_GND)", size=10.5, fill="#444")

    # ---------------- Legend ----------------
    lx, ly = 30, 545
    s.text(lx, ly, "Wire legend (colour + pattern + label)", size=13, weight="bold")
    keys = ["3V3", "GND", "SCLK", "MISO", "SCLK1", "MISO1", "CS_PLATE", "CS_HOUSING", "CS_AIR", "SDA", "SCL", "TCP", "TCN", "USB"]
    for i, k in enumerate(keys):
        colr, dash, lab = NETS[k]
        y = ly + 20 + i * 16
        s.line(lx, y - 4, lx + 40, y - 4, stroke=colr, width=3, dash=dash)
        s.text(lx + 48, y, lab, size=10.5)
    return s.render()


# --------------------------------------------------------------------------------------------------------------
# Housing drawing (three orthographic views, mm)
# --------------------------------------------------------------------------------------------------------------
def housing_svg() -> str:
    h = HOUSING
    d = derived(h)
    W, H = 1400, 1110
    s = Svg(W, H, "WildfireGuardian vehicle unit housing",
            "Front, side and top views of the roof-box concept with dimensions in millimetres: aluminium "
            "enclosure, PTFE radar radome, germanium LWIR window, copper flux plate on ceramic fibre board "
            "proud of the front face, sun and heat shield, base plate and magnet mounts. Concept, unverified.")
    s.text(30, 38, "WildfireGuardian vehicle unit: roof-box housing concept (dimensions in mm)", size=22,
           weight="bold")
    s.text(30, 62, "Design values, not a built or tested part (2026-11-17). Vehicle axes: X forward, Y left, Z up. "
                   "Scale 1.6 px/mm in every view.", size=13, fill="#444")
    k = 1.6
    AL, AL_S = "#e6e9ee", "#3a4250"
    dim_c = "#0b5394"

    def dim_h(x1, x2, y, label, ext_from=None):
        if ext_from is not None:
            s.line(x1, ext_from, x1, y + 4, stroke=dim_c, width=0.8)
            s.line(x2, ext_from, x2, y + 4, stroke=dim_c, width=0.8)
        s.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="1.1" marker-start="url(#arr)" '
              'marker-end="url(#arr)"/>' % (f(x1), f(y), f(x2), f(y), dim_c))
        s.text((x1 + x2) / 2, y - 4, label, size=11, anchor="middle", fill=dim_c)

    def dim_v(x, y1, y2, label, ext_from=None, side="left"):
        if ext_from is not None:
            s.line(ext_from, y1, x - 4 if side == "left" else x + 4, y1, stroke=dim_c, width=0.8)
            s.line(ext_from, y2, x - 4 if side == "left" else x + 4, y2, stroke=dim_c, width=0.8)
        s.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="1.1" marker-start="url(#arr)" '
              'marker-end="url(#arr)"/>' % (f(x), f(y1), f(x), f(y2), dim_c))
        tx = x - 6 if side == "left" else x + 6
        s.text(tx, (y1 + y2) / 2 + 4, label, size=11, anchor="end" if side == "left" else "start", fill=dim_c)

    # ---------------- FRONT VIEW (from ahead; drawing right = vehicle left, +Y) ----------------
    ox, oy = 420, 400  # px of (Y=0, Z=0)
    U = lambda yv: ox + yv * k                     # noqa: E731
    V = lambda zv: oy - zv * k                     # noqa: E731
    s.text(U(0), 100, "FRONT VIEW  (from ahead of the vehicle)", size=14, anchor="middle", weight="bold")
    s.text(U(-h["base_w"] / 2), 118, "<- vehicle right", size=10.5, fill="#555")
    s.text(U(h["base_w"] / 2 + 40), 118, "vehicle left ->", size=10.5, anchor="end", fill="#555")
    s.line(U(-230), V(0), U(230), V(0), stroke="#888", width=1, dash="6 4")
    s.text(U(230), V(0) + 14, "roof skin", size=10, anchor="end", fill="#666")
    for yy in (-h["base_w"] / 2 + 60, h["base_w"] / 2 - 60):
        s.rect(U(yy - h["magnet_d"] / 2), V(h["magnet_h"]), h["magnet_d"] * k, h["magnet_h"] * k,
               fill="#555", stroke="#222", width=1, rx=4)
    s.rect(U(-h["base_w"] / 2), V(d["z_box0"]), h["base_w"] * k, h["base_t"] * k, fill="#c9ced6", stroke=AL_S)
    s.rect(U(-h["box_w"] / 2), V(d["z_box1"]), h["box_w"] * k, h["box_h"] * k, fill=AL, stroke=AL_S, width=2, rx=4)
    sw = h["box_w"] + 2 * h["shield_over"]
    s.rect(U(-sw / 2), V(d["z_sh1"]), sw * k, max(h["shield_t"] * k, 2), fill="#9aa3ad", stroke=AL_S)
    for yy in (-h["box_w"] / 2 + 20, h["box_w"] / 2 - 20):
        s.line(U(yy), V(d["z_box1"]), U(yy), V(d["z_sh0"]), stroke=AL_S, width=3)
    # radome
    rz = d["z_box0"] + h["radome_z"]
    s.rect(U(h["radome_y"] - h["radome_w"] / 2), V(rz + h["radome_h"] / 2), h["radome_w"] * k, h["radome_h"] * k,
           fill="#f7f2d9", stroke="#7a6a1a", width=1.6)
    s.text(U(h["radome_y"]), V(rz) - 4, "PTFE radome", size=10.5, anchor="middle")
    s.text(U(h["radome_y"]), V(rz) + 10, "%.2f mm thick" % d["radome_t"], size=10.5, anchor="middle")
    s.text(U(h["radome_y"]), V(rz) + 24, "(radar AOP behind)", size=9.5, anchor="middle", fill="#555")
    # IR window
    iz = d["z_box0"] + h["ir_win_z"]
    s.circle(U(h["ir_win_y"]), V(iz), h["ir_win_d"] / 2 * k, fill="#d9e4f2", stroke="#22334d", width=1.6)
    s.text(U(h["ir_win_y"]), V(iz) + 4, "Ge", size=11, anchor="middle", weight="bold")
    s.text(U(h["ir_win_y"]), V(iz - h["ir_win_d"] / 2) + 14, "LWIR window", size=10, anchor="middle")
    # plate assembly (outboard on vehicle-left)
    pz = d["z_box0"] + h["plate_z"]
    s.rect(U(h["plate_y"] - h["board_a"] / 2), V(pz + h["board_a"] / 2), h["board_a"] * k, h["board_a"] * k,
           fill="#f2efe6", stroke="#8a7d5a", width=1.2)
    s.rect(U(h["plate_y"] - h["plate_a"] / 2), V(pz + h["plate_a"] / 2), h["plate_a"] * k, h["plate_a"] * k,
           fill="#1a1a1a", stroke="#000", width=1.2)
    s.text(U(h["plate_y"]), V(pz) + 4, "Cu plate", size=10.5, anchor="middle", fill="#fff")
    s.line(U(h["box_w"] / 2), V(pz), U(h["plate_y"] - h["board_a"] / 2), V(pz), stroke=AL_S, width=4)
    # dims
    dim_h(U(-h["box_w"] / 2), U(h["box_w"] / 2), V(0) + 38, "%d" % h["box_w"], ext_from=V(d["z_box0"]))
    dim_h(U(-h["base_w"] / 2), U(h["base_w"] / 2), V(0) + 62, "base %d" % h["base_w"], ext_from=V(d["z_base0"]))
    dim_v(U(-h["base_w"] / 2) - 18, V(d["z_box1"]), V(d["z_box0"]), "%d" % h["box_h"],
          ext_from=U(-h["box_w"] / 2))
    dim_v(U(-h["base_w"] / 2) - 70, V(d["z_sh1"]), V(0), "%d overall" % round(d["z_sh1"]),
          ext_from=U(-sw / 2))
    dim_h(U(h["radome_y"] - h["radome_w"] / 2), U(h["radome_y"] + h["radome_w"] / 2), V(d["z_box1"]) - 12,
          "%d" % h["radome_w"])
    dim_h(U(h["plate_y"] - h["plate_a"] / 2), U(h["plate_y"] + h["plate_a"] / 2), V(pz - h["board_a"] / 2) + 18,
          "plate %d" % h["plate_a"])
    s.text(U(h["plate_y"]), V(pz + h["board_a"] / 2) - 6, "board %d" % h["board_a"], size=10.5,
           anchor="middle", fill=dim_c)
    dim_h(U(h["ir_win_y"] - h["ir_win_d"] / 2), U(h["ir_win_y"] + h["ir_win_d"] / 2), V(d["z_box1"]) - 12,
          "dia %d" % h["ir_win_d"])
    dim_h(U(h["radome_y"]), U(h["ir_win_y"]), V(d["z_box0"] + 6), "%d" % (h["ir_win_y"] - h["radome_y"]))
    s.text(U(0), V(d["z_sh1"]) - 8, "sun / heat shield, 1 mm Al, white top", size=10.5, anchor="middle")

    # ---------------- SIDE VIEW (from vehicle left; drawing left = forward) ----------------
    sx, sy = 1050, 400  # px of (X=0, Z=0)
    U2 = lambda xv: sx - xv * k                    # noqa: E731
    s.text(sx, 100, "SIDE VIEW  (from the vehicle's left)", size=14, anchor="middle", weight="bold")
    s.add('<line x1="%s" y1="118" x2="%s" y2="118" stroke="#333" stroke-width="1.4" marker-end="url(#arr)"/>'
          % (f(sx - 40), f(sx - 120)))
    s.text(sx - 30, 122, "FORWARD (X)", size=10.5, fill="#333")
    s.line(U2(170), V(0), U2(-150), V(0), stroke="#888", width=1, dash="6 4")
    for xx in (-h["base_l"] / 2 + 50, h["base_l"] / 2 - 50):
        s.rect(U2(xx + h["magnet_d"] / 2), V(h["magnet_h"]), h["magnet_d"] * k, h["magnet_h"] * k,
               fill="#555", stroke="#222", width=1, rx=4)
    s.rect(U2(h["base_l"] / 2), V(d["z_box0"]), h["base_l"] * k, h["base_t"] * k, fill="#c9ced6", stroke=AL_S)
    s.rect(U2(h["box_l"] / 2), V(d["z_box1"]), h["box_l"] * k, h["box_h"] * k, fill=AL, stroke=AL_S, width=2, rx=4)
    sl = h["box_l"] + 2 * h["shield_over"]
    s.rect(U2(sl / 2), V(d["z_sh1"]), sl * k, max(h["shield_t"] * k, 2), fill="#9aa3ad", stroke=AL_S)
    for xx in (-h["box_l"] / 2 + 20, h["box_l"] / 2 - 20):
        s.line(U2(xx), V(d["z_box1"]), U2(xx), V(d["z_sh0"]), stroke=AL_S, width=3)
    # plate assembly side profile: plate front at x_plate, board behind it
    s.rect(U2(d["x_plate"] - h["plate_t"]), V(pz + h["board_a"] / 2), h["board_t"] * k, h["board_a"] * k,
           fill="#f2efe6", stroke="#8a7d5a", width=1.2)
    s.rect(U2(d["x_plate"]), V(pz + h["plate_a"] / 2), max(h["plate_t"] * k, 2.5), h["plate_a"] * k,
           fill="#1a1a1a", stroke="#000")
    s.line(U2(d["x_plate"] - h["plate_t"] - h["board_t"]), V(pz), U2(d["x_front"] - 30), V(pz),
           stroke=AL_S, width=4)
    s.text(U2(d["x_plate"]), V(d["z_sh1"]) - 8, "Cu plate + ceramic fibre board", size=10.5)
    # windows (hidden lines on the front face)
    s.line(U2(d["x_front"]), V(rz + h["radome_h"] / 2), U2(d["x_front"]), V(rz - h["radome_h"] / 2),
           stroke="#7a6a1a", width=4)
    s.text(U2(d["x_front"]) + 8, V(rz - h["radome_h"] / 2) + 2, "radome", size=10, fill="#7a6a1a")
    # rear glands
    s.rect(U2(-h["box_l"] / 2) , V(d["z_box0"] + GLAND_Z + 8), 22, 16 * k * 0.6, fill="#444", stroke="#222")
    s.text(U2(-h["box_l"] / 2) + 26, V(d["z_box0"] + GLAND_Z) + 4, "M16 glands (rear)", size=10.5)
    # dims
    dim_h(U2(h["box_l"] / 2), U2(-h["box_l"] / 2), V(0) + 38, "%d" % h["box_l"], ext_from=V(d["z_box0"]))
    dim_h(U2(h["base_l"] / 2), U2(-h["base_l"] / 2), V(0) + 62, "base %d" % h["base_l"],
          ext_from=V(d["z_base0"]))
    dim_h(U2(d["x_plate"]), U2(d["x_front"]), V(pz - h["board_a"] / 2) + 22,
          "%d proud" % h["plate_proud"], ext_from=V(pz - h["plate_a"] / 2))
    dim_v(U2(-sl / 2) + 26, V(d["z_sh0"]), V(d["z_box1"]), "gap %d" % h["shield_gap"], side="right")
    dim_v(U2(d["x_plate"]) - 40, V(pz), V(d["z_box0"]), "%d" % h["plate_z"], ext_from=U2(d["x_plate"]))
    dim_h(U2(d["x_plate"]), U2(d["x_plate"] - h["plate_t"] - h["board_t"]), V(pz + h["board_a"] / 2) - 28,
          "%d+%d" % (h["plate_t"], h["board_t"]))

    # ---------------- TOP VIEW (from above; drawing up = forward, drawing right = vehicle right) ------------
    tx, ty = 420, 800  # px of (X=0, Y=0)
    U3 = lambda yv: tx - yv * k                    # noqa: E731
    V3 = lambda xv: ty - xv * k                    # noqa: E731
    s.text(tx, 545, "TOP VIEW  (shield removed; forward is up)", size=14, anchor="middle", weight="bold")
    s.text(U3(h["base_w"] / 2 + 50), 563, "<- vehicle left", size=10.5, fill="#555")
    s.text(U3(-h["base_w"] / 2), 563, "vehicle right ->", size=10.5, anchor="end", fill="#555")
    s.rect(U3(h["base_w"] / 2), V3(h["base_l"] / 2), h["base_w"] * k, h["base_l"] * k, fill="#c9ced6", stroke=AL_S)
    for yy in (-h["base_w"] / 2 + 60, h["base_w"] / 2 - 60):
        for xx in (-h["base_l"] / 2 + 50, h["base_l"] / 2 - 50):
            s.circle(U3(yy), V3(xx), h["magnet_d"] / 2 * k, fill="none", stroke="#222", width=1.2, dash="5 4")
    s.rect(U3(h["box_w"] / 2), V3(h["box_l"] / 2), h["box_w"] * k, h["box_l"] * k, fill=AL, stroke=AL_S,
           width=2, rx=4)
    s.add('<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="%s" stroke-width="1.2" '
          'stroke-dasharray="10 5"/>' % (f(U3(sw / 2)), f(V3(sl / 2)), f(sw * k), f(sl * k), "#6b7480"))
    s.text(U3(-sw / 2) - 4, V3(sl / 2) + 14, "shield outline", size=10, anchor="end", fill="#6b7480")
    # plate assembly from above
    s.rect(U3(h["plate_y"] + h["board_a"] / 2), V3(d["x_plate"]), h["board_a"] * k, (h["board_t"] + h["plate_t"]) * k,
           fill="#f2efe6", stroke="#8a7d5a", width=1.2)
    s.rect(U3(h["plate_y"] + h["plate_a"] / 2), V3(d["x_plate"]), h["plate_a"] * k, max(h["plate_t"] * k, 2.5),
           fill="#1a1a1a", stroke="#000")
    s.line(U3(h["plate_y"]), V3(d["x_plate"] - h["plate_t"] - h["board_t"]), U3(h["plate_y"]), V3(0),
           stroke=AL_S, width=4)
    s.line(U3(h["plate_y"]), V3(0), U3(h["box_w"] / 2), V3(0), stroke=AL_S, width=4)
    s.text(U3(h["plate_y"]), V3(d["x_plate"]) - 8, "flux plate faces forward", size=10.5, anchor="middle")
    # glands on rear
    for gy in GLAND_Y:
        s.rect(U3(gy) - 8, V3(-h["box_l"] / 2), 16, 14, fill="#444", stroke="#222")
    s.circle(U3(VENT_Y), V3(-h["box_l"] / 2) + 6, 5, fill="#888", stroke="#222")
    s.text(tx, V3(-h["base_l"] / 2) + 18, "rear face: 4 x M16 glands (12 V in, air TC lead, GNSS lead, spare), "
                                         "M12 membrane vent, PC RF window", size=10.5, anchor="middle")
    # radar / camera FOV wedges (illustrative)
    for yy, half, lab in ((h["radome_y"], 60.0, "radar about +/-60 deg"), (h["ir_win_y"], 28.0, "TC001 56 deg")):
        L = 38.0
        a = math.radians(half)
        x0, y0 = U3(yy), V3(h["box_l"] / 2)
        s.poly([(x0 - L * k * math.sin(a), y0 - L * k * math.cos(a)), (x0, y0),
                (x0 + L * k * math.sin(a), y0 - L * k * math.cos(a))], stroke="#b45f06", width=1, dash="3 3")
        s.text(x0, y0 - L * k * math.cos(a) - 6, lab, size=10, anchor="middle", fill="#b45f06")
    dim_h(U3(h["base_w"] / 2), U3(-h["base_w"] / 2), V3(-h["base_l"] / 2) + 48, "base %d" % h["base_w"],
          ext_from=V3(-h["base_l"] / 2))
    dim_v(U3(-h["base_w"] / 2) + 30, V3(h["box_l"] / 2), V3(-h["box_l"] / 2), "%d" % h["box_l"], side="right",
          ext_from=U3(-h["box_w"] / 2))
    dim_v(U3(-h["base_w"] / 2) + 80, V3(h["base_l"] / 2), V3(-h["base_l"] / 2), "base %d" % h["base_l"],
          side="right", ext_from=U3(-h["base_w"] / 2))
    dim_h(U3(h["plate_y"]), U3(0), V3(d["x_plate"]) - 30, "%d" % h["plate_y"])
    s.text(U3(h["base_w"] / 2 - 60), V3(h["base_l"] / 2 - 50) + 4, "magnet dia %d" % h["magnet_d"], size=10,
           anchor="middle", fill=dim_c)

    # ---------------- Notes ----------------
    nx, ny = 850, 560
    s.text(nx, ny, "Notes (all values are design values, unverified)", size=14, weight="bold")
    notes = [
        "Radome: t = n * lambda0 / (2 * sqrt(eps_r)), lambda0 = c / 60 GHz = 5.00 mm.",
        "  polycarbonate eps_r ~ 2.9: n=1 -> 1.47 mm, n=2 -> 2.94 mm",
        "  PTFE eps_r ~ 2.1: n=1 -> 1.72 mm, n=2 -> 3.45 mm (drawn: PTFE n=%d, %.2f mm)"
        % (h["radome_n"], d["radome_t"]),
        "  PTFE preferred near flames (PC softens near 145 C). Check loss with test B.",
        "LWIR window: germanium (AR 8-14 um) or chalcogenide. Glass, PC and acrylic",
        "  are opaque in LWIR. Ge transmission falls when the window runs hot.",
        "Flux plate: copper %d x %d x %d mm, blackened (Pyromark-type, absorptivity"
        % (h["plate_a"], h["plate_a"], h["plate_t"]),
        "  0.95 assumed, to be measured), on %d mm ceramic fibre board so the" % h["board_t"],
        "  thin-skin (lumped) assumption holds; plate isolated from chassis.",
        "Air thermocouple: separate lead to engine-intake height, radiation-shielded.",
        "Shield: %d mm Al, %d mm air gap, %d mm overhang; keeps sun off the lid."
        % (h["shield_t"], h["shield_gap"], h["shield_over"]),
        "Mount: 4 rubber-coated magnets (steel roofs only) plus a tether strap, or",
        "  roof-bar clamps through the base plate. IP65/66 is a target, untested.",
        "Inside the box: Pi, IWR6843AOPEVM, 3 x MAX31855, BNO055, 12->5 V buck.",
        "Aluminium blocks Wi-Fi and GNSS: PC RF window on the rear face, GNSS",
        "  receiver/antenna outside on the roof.",
    ]
    s.lines(nx, ny + 22, notes, size=11, step=16.5)
    return s.render()


def outputs() -> dict:
    return {"wiring.svg": wiring_svg(), "housing.svg": housing_svg()}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    bad = []
    for name, text in outputs().items():
        p = DOCS / name
        if check:
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                bad.append(name)
        else:
            p.write_text(text, encoding="utf-8")
            print("wrote", p)
    if bad:
        print("out of date:", ", ".join(bad), "(run make_drawings.py)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
