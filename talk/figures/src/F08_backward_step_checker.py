"""F08 one backward step and the checker.

Slide 8, full slide. Left: the time-axis diagram of one backward step (four rows). Right: Solver -> Answer +
certificate -> Independent checker, with a tick leaving the checker. Bottom: three numbers read from files.
Sources: research/kcf-theorem/results/{property_tests,mutation_tests}.json; product/wfg-roadlayer README and
golden MANIFEST files.
"""
import re

import style as S
from figkit import add_caption, save
from prov import Ledger
from scene import Scene


def read(L):
    p = "research/kcf-theorem/results/property_tests.json"
    d = L.json(p)
    n = d["counts"]["closure:cases"] + d["counts"]["general:cases"]
    mis = d["mismatches"]
    L.add("Random networks compared with brute force", n, shown=f"{n:,}", file=p,
          field="counts['closure:cases'] + counts['general:cases']", expected="12,000")
    L.add("Disagreements with brute force", mis, shown=str(mis), file=p, field="mismatches", n=f"{n} networks",
          expected="0")
    p2 = "research/kcf-theorem/results/mutation_tests.json"
    m = L.json(p2)
    mutants = [k for k in m if k not in ("cases_per_family", "None")]
    caught = [k for k in mutants if sum(v for kk, v in m[k]["counts"].items() if kk.endswith("cases_caught")) > 0]
    control = sum(v for kk, v in m["None"]["counts"].items() if kk.endswith("cases_caught"))
    L.add("Planted bugs caught", len(caught), shown=f"{len(caught)} of {len(mutants)}", file=p2,
          field="mutants (keys other than 'None', 'cases_per_family') with counts['*:cases_caught'] > 0",
          n=f"{len(mutants)} planted bugs, {m['cases_per_family']} cases per family",
          note=f"unchanged control ('None') caught {control} cases; mutants: {', '.join(mutants)}", expected="5 of 5")
    readme = "product/wfg-roadlayer/README.md"
    txt = L.text(readme)
    k = int(re.search(r"All (\d+) certificates pass", txt).group(1))
    parts = []
    for g in ("uiseong_andong_20250325_1200KST", "yeongdeok_20250325_1800KST"):
        mf = f"product/wfg-roadlayer/golden/{g}/MANIFEST.json"
        parts.append(L.json(mf)["certificates"])
        L.add(f"Certificates in {g}", parts[-1], file=mf, field="certificates")
    assert sum(parts) == k
    L.add("Village certificates passing the independent checker", k, shown=str(k), file=readme,
          field="sentence 'All 174 certificates pass `verify_certificate.py`'", n="84 + 90 golden manifests",
          expected="174",
          note="The count of passes is stated in README prose; tests/test_certificates.py asserts all 84 Uiseong-Andong "
               "pass and samples every 15th Yeongdeok certificate. The manifests give 84 + 90 = 174 certificates.")
    L.add("Random networks per family in the planted-bug test", m["cases_per_family"], file=p2, field="cases_per_family",
          shown=f"{m['cases_per_family']:,}")
    return n, mis, len(caught), len(mutants), k, m["cases_per_family"]


def build(n, mis, caught, nmut, k, cpf):
    sc = Scene("F08_backward_step_checker")
    # ---------------- left: one backward step on a time axis
    x0, x1 = 3.05, 6.30
    lx = 0.50
    X = lambda f: x0 + f * (x1 - x0)  # noqa: E731
    th = 0.24
    rows = [
        ("safe arrival times\nover a road", [(0.42, 0.70), (0.80, 0.95)], S.SAFE, 1.25),
        ("shifted back by\nthe travel time", [(0.20, 0.48), (0.58, 0.73)], S.SAFE, 2.15),
        ("closed:\nfire on the road", [(0.36, 0.62)], S.FIRE, 3.05),
        ("safe start times", [(0.20, 0.36), (0.62, 0.73)], S.SAFE, 3.95),
    ]
    for i, (lab, segs, col, y) in enumerate(rows):
        g = f"row {i + 1}: {lab}".replace("\n", " ")
        sc.text(lx, y + th / 2, lab, name=f"{g} label", group=g)
        sc.rect(x0, y, x1 - x0, th, fill=S.WHITE, edge=S.INK, lw=0.75, name=f"{g} track", group=g)
        for j, (a, b) in enumerate(segs):
            sc.rect(X(a), y, X(b) - X(a), th, fill=col, edge=S.INK, lw=0.75, name=f"{g} interval {j + 1}", group=g)
    # shift arrows from row 1 to row 2 (travel time)
    for (a, _), (c, _) in zip(rows[0][1], rows[1][1]):
        sc.line([(X(a), 1.25 + th + 0.06), (X(c) + 0.02, 2.15 - 0.06)], color=S.INK, lw=1.2, arrow=True, head=0.10,
                name=f"shift arrow {a}", group="travel-time shift")
    # dashed guides at the closure edges, row 3 down to row 4
    for f in rows[2][1][0]:
        sc.line([(X(f), 3.05 + th + 0.04), (X(f), 3.95 - 0.04)], color=S.FIRE, lw=1.2, dash=(3, 2),
                name=f"closure edge {f}", group="closure guides")
    # time axis
    sc.line([(x0, 4.62), (x1, 4.62)], color=S.INK, lw=1.2, arrow=True, head=0.12, name="time axis", group="time axis")
    sc.text(x1 - 0.70, 4.95, "time", color=S.MID, name="time axis label", group="time axis")

    # ---------------- right: solver, answer + certificate, independent checker
    by, bh = 2.05, 1.05
    boxes = [("Solver", 6.95, 1.25, S.TINT_ROUTING), ("Answer +\ncertificate", 8.70, 1.75, S.TINT_OUTPUT),
             ("Independent\nchecker", 10.95, 1.95, S.WHITE)]
    for lab, bx, bw, tint in boxes:
        g = lab.replace("\n", " ")
        sc.rect(bx, by, bw, bh, fill=tint, edge=S.INK, lw=0.75, name=f"{g} box", group=g, role="box")
        sc.text(bx + bw / 2, by + bh / 2, lab, ha="center", name=f"{g} label", group=g)
    # arrows
    sc.line([(6.95 + 1.25 + 0.06, by + bh / 2), (8.70 - 0.06, by + bh / 2)], color=S.INK, lw=1.0, arrow=True,
            head=0.10, name="solver to answer", group="arrows")
    sc.line([(8.70 + 1.75 + 0.06, by + bh / 2), (10.95 - 0.06, by + bh / 2)], color=S.INK, lw=1.0, arrow=True,
            head=0.10, name="certificate to checker", group="arrows")
    # tick leaving the checker, below it
    cx = 10.95 + 1.95 / 2
    sc.line([(cx, by + bh + 0.06), (cx, by + bh + 0.55)], color=S.SAFE, lw=1.0, arrow=True, head=0.10,
            name="checker output arrow", group="checker result")
    sc.tick(cx, by + bh + 0.92, 0.42, color=S.SAFE, lw=2.5, name="tick mark", group="checker result")
    sc.text(12.90, by + bh + 1.62, "shares no code with the solver", ha="right", color=S.INK,
            name="checker note", group="checker result")

    return sc


def main():
    L = Ledger("F08", "One backward step and the checker")
    vals = read(L)
    L.note("The left-hand time diagram is a schematic; its intervals carry no numbers.")
    L.save()
    sc = build(*vals)
    fig = S.new_figure()
    sc.draw(fig)
    n, mis, caught, nmut, k, cpf = vals
    S.panel_letter(fig, 0.45, 0.6, "a")
    S.panel_letter(fig, 6.95, 0.6, "b")
    cap = add_caption(fig, (
        "Figure 8. (a) One backward step: the times at which a traveller can safely arrive over a road are shifted back "
        "by the travel time, and the times when fire is on the road are removed, leaving the safe start times (two "
        "windows with a gap). (b) The solver returns an answer with a certificate, which an independent checker that "
        f"shares no code with the solver accepts or rejects. Tests: {mis} disagreements with brute force on {n:,} "
        f"random networks; {caught} of {nmut} planted bugs caught ({cpf:,} networks per family); all {k} village "
        "certificates of the worked examples pass the checker. Source: research/kcf-theorem, product/wfg-roadlayer."),
        x_in=0.45, width_in=12.45, top_in=5.8)
    sc.save_spec(fig)
    save(fig, "F08_backward_step_checker", kind="scene", caption=cap)


if __name__ == "__main__":
    main()
