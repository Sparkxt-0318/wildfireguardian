"""Design tokens for the booth screen and the overlay video.

Rules (PLAN.md section 3, user's 2 m rule): black background, white type, green for every
measured value, orange only for embers and their tracks. On a 1920x1080 screen the main
values are at least 96 px tall, card labels at least 28 px and small tags at least 18 px.
Sizes scale with the screen height.
"""
from __future__ import annotations

BG = "#000000"
INK = "#FFFFFF"
INK2 = "#8E8E93"          # secondary text
INK3 = "#48484A"          # hairlines, inactive
PANEL = "#0B0B0D"
BAND = "#3A3A3C"          # status bands (replay, reconnecting)
GREEN = "#30D158"         # measured values
ORANGE = "#FF9F0A"        # embers and tracks
ORANGE_CORE = "#FFD60A"   # hottest core of an ember mark

REF_HEIGHT = 1080


def px(size_at_1080: float, height: int) -> int:
    """Scale a pixel size defined for a 1080 px tall screen."""
    return max(1, int(round(size_at_1080 * height / REF_HEIGHT)))


SIZES = {
    "value": 104,          # main card numbers (at least 96 at 1080)
    "unit": 30,
    "label": 30,           # card labels (at least 28)
    "tag": 20,             # small tags such as Estimate, Uncalibrated (at least 18)
    "status": 20,
    "band": 34,
    "title": 26,
    "limits_title": 40,
    "limits_body": 28,
    "margin": 40,
}


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio between two hex colors."""
    def lum(h: str) -> float:
        h = h.lstrip("#")
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)
