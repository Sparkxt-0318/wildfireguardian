"""Register the vendored Pretendard fonts with Qt.

Qt falls back to Apple SD Gothic Neo on macOS (and any installed CJK font on Linux) for
glyphs Pretendard lacks, so families are always given as a list.
"""
from __future__ import annotations

from wfglink import PROJECT_ROOT

FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
FAMILY = "Pretendard"
FALLBACKS = ["Pretendard", "Apple SD Gothic Neo", "Noto Sans CJK KR", "Noto Sans KR"]

_loaded: list[str] | None = None


def load_fonts() -> list[str]:
    """Load every OTF in assets/fonts once. Requires a QGuiApplication. Returns families."""
    global _loaded
    if _loaded is not None:
        return _loaded
    from PySide6.QtGui import QFontDatabase

    families: set[str] = set()
    for path in sorted(FONT_DIR.glob("*.otf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families.update(QFontDatabase.applicationFontFamilies(font_id))
    _loaded = sorted(families)
    return _loaded


def ui_font(pixel_size: int, weight: str = "regular"):
    """QFont with Pretendard first and Hangul-capable fallbacks, sized in pixels."""
    from PySide6.QtGui import QFont

    load_fonts()
    font = QFont()
    font.setFamilies(FALLBACKS)
    font.setPixelSize(int(pixel_size))
    font.setWeight({
        "regular": QFont.Weight.Normal,
        "medium": QFont.Weight.Medium,
        "semibold": QFont.Weight.DemiBold,
        "bold": QFont.Weight.Bold,
    }[weight])
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font
