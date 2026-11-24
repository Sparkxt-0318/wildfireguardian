"""F11a village card: one real card exported from the road layer, in Korean as printed.

Not a new figure. Page 86 of product/wfg-roadlayer/examples/cards/yeongdeok_20250325_1800KST/
cards_ko_yeongdeok_2025.pdf (삼의리 Samui-ri, the village of F02), rendered at 300 dpi with pdftoppm and cropped to the
card. The caption is a separate text item (PowerPoint text box), not part of the picture.
"""
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

import style as S
from prov import Ledger

PDF = "product/wfg-roadlayer/examples/cards/yeongdeok_20250325_1800KST/cards_ko_yeongdeok_2025.pdf"
PAGE = 86


def main():
    L = Ledger("F11a", "Village card (exported as printed)")
    head = subprocess.run(["pdftotext", "-f", str(PAGE), "-l", str(PAGE), "-layout", str(S.REPO / PDF), "-"],
                          capture_output=True, text=True, check=True).stdout
    assert "삼의리" in head, "page no longer holds the Samui-ri card"
    L.add("Card exported", f"page {PAGE} (삼의리)", file=PDF, field=f"page {PAGE}, rendered at 300 dpi")
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-f", str(PAGE), "-l", str(PAGE), "-r", "300", "-png", str(S.REPO / PDF),
                        f"{td}/p"], check=True)
        src = next(Path(td).glob("p*.png"))
        im = Image.open(src).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bbox = ImageChops.difference(im, bg).getbbox()
    pad = 30
    box = (max(bbox[0] - pad, 0), max(bbox[1] - pad, 0), min(bbox[2] + pad, im.width), min(bbox[3] + pad, im.height))
    card = im.crop(box)
    out = S.FIGDIR / "F11a_village_card.png"
    card.save(out, dpi=(300, 300))
    caption = ("Figure 11. A village card as printed by the road layer, for 삼의리 Samui-ri (영덕 Yeongdeok region), "
               "forecast issued 25 March 2025, 18:00 KST. Model output, for reference only. "
               f"Source: {PDF}, page {PAGE}.")
    (S.BUILD / "F11a_village_card_layout.json").write_text(json.dumps(
        {"name": "F11a_village_card", "kind": "image", "image": out.name, "size_px": card.size,
         "texts": [{"text": caption, "caption": True, "name": "Caption"}]}, ensure_ascii=False, indent=1))
    L.note(f"Cropped to {card.size[0]} x {card.size[1]} px at 300 dpi.")
    L.save()
    print(f"F11a_village_card: {card.size}")


if __name__ == "__main__":
    main()
