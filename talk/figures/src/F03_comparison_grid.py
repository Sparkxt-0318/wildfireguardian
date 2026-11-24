"""F03 comparison grid: a three-rule table drawn as a figure (native shapes in PowerPoint).

Slide 3, full slide. Filled circle = provided, empty circle = not provided. Our row in blue.
No market-research summary is committed under research/ (searched for Technosylva, Genasys, Watch Duty on every
ref), so the cell values are the ones given in the talk brief (DECISIONS.md D17).
"""
import style as S
from figkit import add_caption, save
from prov import Ledger
from scene import Scene

COLS = ["where the\nfire is", "who to\nalert", "when each village's\nlast road closes", "answer can\nbe checked"]
ROWS = [
    ("Korea's spread prediction system\n(5-hour and 8-hour zones)", [1, 1, 0, 0], False),
    ("Technosylva", [1, 0, 0, 0], False),
    ("Genasys Protect", [0, 1, 0, 0], False),
    ("Watch Duty", [1, 1, 0, 0], False),
    ("WildfireGuardian (ours)", [0, 0, 1, 1], True),
]


def build():
    sc = Scene("F03_comparison_grid")
    x0, x1 = 0.6, 12.75
    c0 = 5.55                      # first data column centre
    dc = 2.15
    y_top = 0.75
    head_h = 0.95
    row_h = 0.82
    sc.line([(x0, y_top), (x1, y_top)], color=S.INK, lw=1.4, name="top rule", group="rules")
    for j, c in enumerate(COLS):
        sc.text(c0 + j * dc, y_top + head_h / 2, c, ha="center", name=f"column {j + 1} header",
                group="header")
    sc.text(x0, y_top + head_h / 2, "system", name="row header", group="header")
    y_mid = y_top + head_h
    sc.line([(x0, y_mid), (x1, y_mid)], color=S.INK, lw=0.75, name="header rule", group="rules")
    for i, (name, vals, ours) in enumerate(ROWS):
        cy = y_mid + row_h * (i + 0.5)
        col = S.OURS if ours else S.INK
        g = f"row {i + 1}: {name.splitlines()[0]}"
        sc.text(x0, cy, name, color=col, name=f"{g} label", group=g)
        for j, v in enumerate(vals):
            sc.circle(c0 + j * dc, cy, 0.13, fill=col if v else S.WHITE, edge=col, lw=1.2,
                      name=f"{g} {COLS[j].replace(chr(10), ' ')} {'yes' if v else 'no'}", group=g)
    y_bot = y_mid + row_h * len(ROWS)
    sc.line([(x0, y_bot), (x1, y_bot)], color=S.INK, lw=1.4, name="bottom rule", group="rules")
    return sc


def main():
    L = Ledger("F03", "Comparison grid")
    L.note("Cell values from the talk brief (prompt 60), not from a committed file: no market-research summary is "
           "committed. Korea 1,1,0,0; Technosylva 1,0,0,0; Genasys 0,1,0,0; Watch Duty 1,1,0,0; WildfireGuardian 0,0,1,1.")
    L.save()
    sc = build()
    fig = S.new_figure()
    sc.draw(fig)
    cap = add_caption(fig, "Figure 3. What each system reports. Filled circle: provided; empty circle: not provided. "
                           "From public documentation; internal agency systems could not be inspected.",
                      x_in=0.6, width_in=12.15, top_in=6.25)
    sc.save_spec(fig)
    save(fig, "F03_comparison_grid", kind="scene", caption=cap)


if __name__ == "__main__":
    main()
