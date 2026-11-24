"""SOURCES.md, README.md, contact_sheet.png and kcf_talk_figures.zip from the build manifests."""
import json
import zipfile

from PIL import Image, ImageDraw, ImageFont

import style as S
from style import BUILD, FIGDIR

FIGS = [
    # code, file stem, slide, what it shows, status
    ("F01", "F01_title_map", "1 (right half)", "Uiseong–Andong replay area at 12:00 KST, 25 Mar 2025: roads, forecast fire, villages by time left", "done"),
    ("F02", "F02_road_cut", "2 (right two thirds)", "Samui-ri time axis (road cut 159.6 min before the fire) and the gap histogram (n = 97)", "done (native histogram in pptx)"),
    ("F03", "F03_comparison_grid", "3 (full)", "Three-rule comparison table: Korea, Technosylva, Genasys, Watch Duty, WildfireGuardian", "done with a note: cells from the brief (D18)"),
    ("F04", "F04_overview", "5 (full)", "Method overview, one case left to right (Uiseong–Andong, 18:00 KST): inputs, M548 forecast and kernels, exposure, safety distance and gate, routing, village card and checker", "done with notes: (c) shows Fish Creek, no Korean fuel maps (D30); (d)–(f) come from the replay, not from (b) (D31); 17 in canvas, PNG 300 dpi transparent (D33)"),
    ("F05", "F05_data_foundation", "4 (full)", "Data foundation: label tiers (207,508), onset leads (45 of 240), one reversible patch", "done with a note: panel (b) shows the leads, not one fire's signal (D20)"),
    ("F06", "F06_safety_distance", "6 (right two thirds)", "5-hour reach of 28 California fires, safety distance 3.75 km, Gyeongbuk hours withheld", "done"),
    ("F12", "F12_forecast_example", "6 (full width)", "Wapiti 2024 forecast example (three panels) and scores over 25 intervals", "done"),
    ("F07", "F07_forward_backward", "7 (full)", "Forward search from one village against one backward pass from the shelters (schematic)", "done (native shapes in pptx)"),
    ("F15", "F15_exposure", "7 (full width)", "Fish Creek exposure maps across the slide: chance you cannot see 10 m, fine smoke, CO; burned area, north arrow, scale bar, labels at the highest values (D35)", "done with a note: rebuilt from screenshots, colour-bar ticks typed in by eye (D26); redo from the arrays when they arrive"),
    ("F16", "F16_safety_zones", "7 (right half)", "d = 4H geometry and the distribution of d* (13,125 cells below 375 m)", "done with a note: largest d* 323 m in the file, 320 m expected (D22)"),
    ("F17", "F17_heat_terrain", "backup", "Heat on terrain (3D)", "not done: terrain and thermal arrays not on this machine (NEEDS.md)"),
    ("F08", "F08_backward_step_checker", "8 (full)", "One backward step on a time axis; solver, certificate and independent checker", "done (native shapes in pptx)"),
    ("F09", "F09_speed", "9 (full width)", "Search per village (earlier) against one backward pass (ours): six forecast hours in KST with place and check counts, total (129×), line at the hourly update (D36)", "done"),
    ("F09b", "F09b_speed_fastpath", "9 (variant, full)", "F09 plus the scalar fast path as its own panel (other machine); rows and names as F09 (D36)", "done"),
    ("F10", "F10_camp_fire", "10 (full)", "Camp Fire: 170 of 195 road-closed reports caught, minutes early, cost 22 of 23", "done with a note: no road lines (D12); median of caught = 153 min (D13)"),
    ("F11a", "F11a_village_card", "11", "One real village card (삼의리 Samui-ri), exported at 300 dpi as printed", "done"),
    ("F13", "F13_kernels", "backup", "Four mean effective kernels and their embedded sum (h⁻¹)", "done with a note: rebuilt from the preprint's vector PDF, calibrated to its table (D24)"),
    ("F14", "F14_reliability", "backup", "Reliability of the reported model, low-probability region enlarged", "done"),
]


def sources_md():
    out = ["# SOURCES", "",
           "Every number printed or plotted, read by script from the file named. `commit` is the last commit that "
           "touched the file (wildfireguardian: `git log -1`; wildfireguardiandata: GitHub commits API); files outside "
           "a git repository are identified by SHA-256. Rows marked **DIFFERENT FROM EXPECTED** give the file value, "
           "which is what the figure shows.", "",
           "Machines: F09 and panel (a) of F09b were timed on kcf-bench host B (Intel Xeon 2.10 GHz, one core); panel "
           "(b) of F09b on an Apple M5 Pro laptop under load (research/kcf-fastpath, runs/HOST.json). They come from "
           "different machines and do not share an axis.", ""]
    for code, stem, *_ in FIGS:
        p = BUILD / f"{code}_sources.json"
        if not p.exists():
            out += [f"## {code}", "", "Not built (see README.md).", ""]
            continue
        d = json.loads(p.read_text())
        out += [f"## {code}: {d['title']}", "", "| shown | value | n | file | field | repo / ref / commit | expected | note |",
                "|---|---|---|---|---|---|---|---|"]
        for r in d["rows"]:
            v = r["value"]
            if isinstance(v, float):
                v = f"{v:.6g}"
            elif isinstance(v, list):
                v = ", ".join(f"{x:.6g}" if isinstance(x, float) else str(x) for x in v)
            cell = lambda x: str(x if x not in (None, "") else "").replace("|", "\\|").replace("\n", " ")  # noqa: E731
            out.append("| " + " | ".join(cell(x) for x in [
                f"**{r['label']}**" + (f" ({r['shown']})" if r.get("shown") else ""),
                f"{v} {r.get('unit') or ''}".strip(), r.get("n"), f"`{r['file']}`", r["field"],
                f"{r['repo']} / {r['ref']} / `{r['commit']}`", r.get("expected"), r.get("note")]) + " |")
        for n in d.get("notes", []):
            out.append(f"\n- {n}")
        out.append("")
    (FIGDIR / "SOURCES.md").write_text("\n".join(out))


def readme():
    rows = ["| code | slide | files | what it shows | status |", "|---|---|---|---|---|"]
    for code, stem, slide, what, status in FIGS:
        have = (FIGDIR / f"{stem}.png").exists()
        files = (f"`{stem}.{{svg,pdf,png}}`, `{stem}_nocaption.*`, `{stem}_notext.{{png,svg}}`" if have and code != "F11a"
                 else (f"`{stem}.png`" if have else "none"))
        rows.append(f"| {code} | {slide} | {files} | {what} | {status} |")
    txt = f"""# Talk figures (Korea Code Fair, 10-minute talk)

Branch `talk/figures` (not merged). Every figure is made by one script in `src/`, reads its numbers from committed
result files through `src/prov.py`, and writes a ledger used for `SOURCES.md`. Decisions are in `DECISIONS.md`; missing
inputs in `NEEDS.md`.

| file | what |
|---|---|
| `Fxx_name.svg/.pdf/.png` | complete figure with its numbered caption (PNG 3840 px wide; PDF fonts embedded) |
| `Fxx_name_nocaption.*` | the same without the caption |
| `Fxx_name_notext.png/.svg` | the same graphic with every word and number removed (same size and position) |
| `kcf_talk_figures.pptx` | one figure per slide, editable: schematics as native shapes, F02 and F05 (a) as native charts, every label and caption a text box; last slide = palette |
| `contact_sheet.png` | every figure with its code |
| `kcf_talk_figures.zip` | the pptx plus all PNG, SVG and PDF files |
| `check/` | greyscale versions and the collision-check result of each figure |

## Figures

{chr(10).join(rows)}

## Rebuild

```
bash talk/figures/make_all.sh
```

needs Python 3 with matplotlib, numpy, pandas, pillow, python-pptx, pyproj, tifffile (the script creates `.venv-fig`),
`pdftoppm`/`pdftotext` (poppler), `gh` (for the read-only wildfireguardiandata files, cached in `.cache/`, not
committed), and LibreOffice for the render check (`tools/check_pptx.sh`, which points LibreOffice at the macOS system
fonts with `tools/fonts.conf.template`; without it LibreOffice's headless mode falls back to its own serif fonts).

## Style

Research-paper style (revision of 24 Nov): framed axes with light gridlines, one text size (16 pt) and 18 pt axis
titles, boxed legends, whiskers wherever the source has an interval, (a)/(b) panel letters, numbered captions carrying
the headline numbers and caveats, square-cornered schematic boxes with 0.75 pt outlines. Palette and fonts in
`src/style.py` (Helvetica Neue; Inter is not installed; NanumGothic for Korean). Each script fails if any text comes
within 4 pt of another text, a data mark, an axis or the canvas edge (`src/figkit.py`).
"""
    (FIGDIR / "README.md").write_text(txt)


def contact_sheet():
    tiles = [(code, FIGDIR / f"{stem}.png") for code, stem, *_ in FIGS if (FIGDIR / f"{stem}.png").exists()]
    tw, th = 960, 540
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 50)), "white")
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 30)
    except OSError:
        font = ImageFont.load_default()
    for i, (code, p) in enumerate(tiles):
        im = Image.open(p).convert("RGB")
        im.thumbnail((tw - 20, th - 10))
        x, y = (i % cols) * tw, (i // cols) * (th + 50)
        sheet.paste(im, (x + (tw - im.width) // 2, y + 45))
        d.rectangle([x + 4, y + 44, x + tw - 4, y + th + 44], outline=(200, 200, 200))
        d.text((x + 10, y + 6), code, fill=(26, 26, 26), font=font)
    sheet.save(FIGDIR / "contact_sheet.png")


def zip_all():
    """The pptx, every figure file (complete, no caption, text-free; PNG, SVG, PDF), the contact sheet and the docs."""
    with zipfile.ZipFile(FIGDIR / "kcf_talk_figures.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(FIGDIR / "kcf_talk_figures.pptx", "kcf_talk_figures.pptx")
        for ext in ("png", "svg", "pdf"):
            for p in sorted(FIGDIR.glob(f"F*.{ext}")):
                z.write(p, f"figures/{p.name}")
        for name in ("contact_sheet.png", "README.md", "SOURCES.md", "DECISIONS.md", "NEEDS.md"):
            if (FIGDIR / name).exists():
                z.write(FIGDIR / name, name)


if __name__ == "__main__":
    sources_md()
    readme()
    contact_sheet()
    zip_all()
    print("wrote SOURCES.md, README.md, contact_sheet.png, kcf_talk_figures.zip")
