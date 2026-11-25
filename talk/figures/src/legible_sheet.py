"""Contact sheet of talk/figures/kcf_legible/: every figure scaled to its slot (slide px), on paper, with its name and
slot. Written to kcf_legible/contact_sheet.png."""
from PIL import Image, ImageDraw, ImageFont

import legible as G
import style as S

ROWS = [["F04a_overview_forecast"], ["F04b_overview_roads"], ["F07_map"], ["F08_map", "F12_forecast_maps"],
        ["F14_reliability", "F09_speed"], ["F10_camp_fire"]]
PAD, HEAD = 30, 44


def main():
    font = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 28)
    width = max(sum(G.SLOTS[n][0] for n in r) + PAD * (len(r) + 1) for r in ROWS)
    height = sum(max(G.SLOTS[n][1] for n in r) + HEAD + PAD for r in ROWS) + PAD
    sheet = Image.new("RGB", (width, height), S.PAPER)
    d = ImageDraw.Draw(sheet)
    y = PAD
    for r in ROWS:
        x = PAD
        for n in r:
            w, h = G.SLOTS[n]
            im = Image.open(G.OUT / f"{n}.png").convert("RGBA").resize((w, h), Image.LANCZOS)
            d.text((x, y), f"{n}  ({w} x {h})", fill=S.GREY, font=font)
            d.rectangle([x - 1, y + HEAD - 1, x + w, y + HEAD + h], outline="#D0CCC2")
            sheet.paste(im, (x, y + HEAD), im)
            x += w + PAD
        y += max(G.SLOTS[n][1] for n in r) + HEAD + PAD
    sheet.save(G.OUT / "contact_sheet.png")
    print("contact sheet", sheet.size)


if __name__ == "__main__":
    main()
