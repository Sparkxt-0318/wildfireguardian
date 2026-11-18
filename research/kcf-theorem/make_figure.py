"""Figure: the 6-node toy (research/kcf-evidence/ALGORITHM_APPENDIX.md) with the backward pass drawn step by step.

Runs the repository's unchanged deadline_field.core.backward and records, by wrapping its heap and interval-insert
calls, every pop and every piece added. Writes figures/toy_backward_pass.svg (standard library only).

    python3 research/kcf-theorem/make_figure.py
"""
from __future__ import annotations

import heapq as _hq
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness-2026-11" / "F-3.1"))
from deadline_field import core  # noqa: E402
from deadline_field import intervals as iv  # noqa: E402

H = 60
NAMES = ["e0", "e1", "e2", "e3", "e4", "e5", "e6"]
TAIL = [0, 1, 0, 2, 3, 1, 4]
HEAD = [1, 5, 2, 3, 5, 4, 5]
D = [10, 10, 15, 15, 15, 5, 8]
B = [[], [(18, 60)], [], [], [], [], [(14, 40)]]
A = [[], [(0, 55)], [], [], [(0, 55)], [], [(0, 55)]]


def trace():
    events = []

    class HeapShim:
        heappush = staticmethod(_hq.heappush)

        @staticmethod
        def heappop(h):
            item = _hq.heappop(h)
            events.append(("pop", item[1], (item[2], item[3])))
            return item

    real_add = iv.add

    def add(lst, piece):
        events.append(("add", lst, piece))
        return real_add(lst, piece)

    core.heapq, core.iv.add = HeapShim, add
    try:
        inst = core.Instance(H=H, n_nodes=6, tail=TAIL, head=HEAD, D=D, waitable=[False] * 6, B=B, A=A)
        fld = core.backward(inst)
    finally:
        core.heapq, core.iv.add = _hq, real_add
    steps, cur = [], None
    for ev in events:
        if ev[0] == "pop":
            cur = {"j": ev[1], "piece": ev[2], "adds": []}
            steps.append(cur)
        else:
            s = next(i for i, r in enumerate(fld.R) if r is ev[1])
            cur["adds"].append((s, ev[2]))
    return fld, steps, core.issue_set(fld, 0)


def svg(fld, steps, origin_set):
    W_, X0, X1 = 1240, 640, 1180
    sx = lambda t: X0 + (X1 - X0) * t / H  # noqa: E731
    out = []
    p = out.append
    rows = [st for st in steps if any(TAIL[st["j"]] == HEAD[s] for s in range(7))]
    row_h, top = 58, 120
    height = top + row_h * (len(rows) + 1) + 70
    p(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W_} {height}" width="{W_}" height="{height}" '
      'font-family="Helvetica, Arial, sans-serif" font-size="12">')
    p('<defs><pattern id="fl" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
      '<rect width="6" height="6" fill="#fde2e1"/><line x1="0" y1="0" x2="0" y2="6" stroke="#d64541" '
      'stroke-width="2.5"/></pattern>'
      '<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
      '<path d="M0,0 L10,5 L0,10 z" fill="#555"/></marker></defs>')
    p(f'<rect width="{W_}" height="{height}" fill="#ffffff"/>')
    p('<text x="20" y="28" font-size="16" font-weight="bold">Backward pass on the 6-node toy (H = 60 s), '
      'as executed by deadline_field.core.backward</text>')
    p('<text x="20" y="48" fill="#444">Each row is one heap pop: a piece of G_j is shifted back by the travel time '
      'D_j, the seconds at which edge j is closed (B_j) are removed,</text>')
    p('<text x="20" y="64" fill="#444">and what is left is added to R_s for every edge s into tail(j). Pops that '
      'have no predecessor (edges out of the origin) are omitted.</text>')
    # graph (left column, x < 330)
    pos = {0: (40, 120), 1: (130, 30), 4: (250, 30), 5: (290, 150), 2: (110, 250), 3: (240, 250)}
    labels = {0: (62, 70, "end"), 1: (215, 112, "end"), 2: (55, 200, "middle"), 3: (175, 272, "middle"),
              4: (290, 210, "start"), 5: (190, 20, "middle"), 6: (285, 85, "start")}
    gy = top + 10
    p(f'<text x="20" y="{gy}" font-weight="bold">Road graph</text>')
    p(f'<g transform="translate(0,{gy + 30})">')
    for j in range(7):
        (x1, y1), (x2, y2) = pos[TAIL[j]], pos[HEAD[j]]
        dx, dy = x2 - x1, y2 - y1
        n = (dx * dx + dy * dy) ** 0.5
        ax, ay, bx, by = x1 + dx / n * 15, y1 + dy / n * 15, x2 - dx / n * 17, y2 - dy / n * 17
        col = "#d64541" if B[j] else "#555"
        p(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{col}" stroke-width="2" '
          'marker-end="url(#ar)"/>')
        lx, ly, anc = labels[j]
        p(f'<text x="{lx}" y="{ly}" text-anchor="{anc}" font-size="11" fill="{col}">{NAMES[j]}: {D[j]} s</text>')
        if B[j]:
            p(f'<text x="{lx}" y="{ly + 13}" text-anchor="{anc}" font-size="11" fill="{col}">closed '
              f'{B[j][0][0]}–{B[j][0][1]}</text>')
    for v, (x, y) in pos.items():
        fill = "#e8f1fb" if v != 5 else "#e3f4e6"
        p(f'<circle cx="{x}" cy="{y}" r="14" fill="{fill}" stroke="#333" stroke-width="1.5"/>'
          f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-weight="bold">{v}</text>')
    p(f'<text x="{pos[0][0]}" y="{pos[0][1] + 30}" text-anchor="middle" font-size="11">origin</text>')
    p(f'<text x="{pos[5][0]}" y="{pos[5][1] + 30}" text-anchor="middle" font-size="11">shelter</text>')
    p('</g>')
    notes = ["Edge label: travel time D; \"closed a–b\":", "start seconds a..b touch flame (B).",
             "Arrival over e1, e4, e6 is accepted", "at 0–55 (5 s stay ends by H = 60).", "No node is waitable."]
    for k, line in enumerate(notes):
        p(f'<text x="20" y="{gy + 340 + 15 * k}" font-size="11" fill="#444">{line}</text>')
    # axis
    ay = top - 8
    for t in range(0, H + 1, 10):
        p(f'<line x1="{sx(t):.1f}" y1="{ay}" x2="{sx(t):.1f}" y2="{height - 50}" stroke="#eee"/>'
          f'<text x="{sx(t):.1f}" y="{ay - 4}" text-anchor="middle" fill="#666">{t}</text>')
    p(f'<text x="{X1 + 8}" y="{ay - 4}" fill="#666">s</text>')
    for k, st in enumerate(rows):
        y = top + k * row_h
        j, (lo, hi) = st["j"], st["piece"]
        src = "A" if (lo, hi) in A[j] else "R"
        preds = [s for s in range(7) if HEAD[s] == TAIL[j]]
        p(f'<text x="{X0 - 10}" y="{y + 12}" text-anchor="end" font-weight="bold">step {k + 1}: pop G_{NAMES[j]} '
          f'piece [{lo},{hi}] ({src})</text>')
        p(f'<text x="{X0 - 10}" y="{y + 27}" text-anchor="end" fill="#444">shift −{D[j]}, minus B_{NAMES[j]}'
          f' → R of {", ".join(NAMES[s] for s in preds)}</text>')
        p(f'<rect x="{sx(lo):.1f}" y="{y}" width="{sx(hi) - sx(lo):.1f}" height="10" fill="#b8b8b8"/>')
        a, b = max(lo - D[j], 0), hi - D[j]
        p(f'<rect x="{sx(a):.1f}" y="{y + 14}" width="{sx(b) - sx(a):.1f}" height="10" fill="none" '
          'stroke="#666" stroke-dasharray="3,2"/>')
        for blo, bhi in B[j]:
            clo_, chi_ = max(blo, a), min(bhi, b)
            if clo_ <= chi_:
                p(f'<rect x="{sx(clo_):.1f}" y="{y + 14}" width="{sx(chi_) - sx(clo_):.1f}" height="10" '
                  'fill="url(#fl)" opacity="0.9"/>')
        cand = iv.subtract((a, b), B[j]) if a <= b else []
        added = {q for _, q in st["adds"]}
        for clo, chi in cand:
            new = any(q[0] >= clo and q[1] <= chi for q in added)
            col = "#2b6cb0" if new else "#9fb7d0"
            p(f'<rect x="{sx(clo):.1f}" y="{y + 28}" width="{max(sx(chi) - sx(clo), 2):.1f}" height="10" '
              f'fill="{col}"/>')
            tag = f"[{clo},{chi}]" + ("" if new else " already in R")
            p(f'<text x="{sx(chi) + 6:.1f}" y="{y + 37}" font-size="11" fill="{col}">{tag}</text>')
    y = top + len(rows) * row_h
    p(f'<text x="{X0 - 10}" y="{y + 12}" text-anchor="end" font-weight="bold">read-off at origin 0</text>')
    p(f'<text x="{X0 - 10}" y="{y + 27}" text-anchor="end" fill="#444">(G_e0 − 10) ∪ (G_e2 − 15)</text>')
    for lo, hi in origin_set:
        p(f'<rect x="{sx(lo):.1f}" y="{y + 4}" width="{sx(hi) - sx(lo):.1f}" height="14" fill="#2f855a"/>'
          f'<text x="{(sx(lo) + sx(hi)) / 2:.1f}" y="{y + 32}" text-anchor="middle" fill="#2f855a">{lo}–{hi}</text>')
    p(f'<text x="{sx(18):.1f}" y="{y + 15}" text-anchor="middle" fill="#a33">hole 11–25</text>')
    ly = height - 28
    items = [("#b8b8b8", "popped piece of G_j"), (None, "shifted back by D_j"), ("url(#fl)", "closed (B_j)"),
             ("#2b6cb0", "new in R_s"), ("#2f855a", "feasible departures: not a prefix")]
    x = 20
    for col, lab in items:
        if col:
            p(f'<rect x="{x}" y="{ly - 10}" width="22" height="10" fill="{col}"/>')
        else:
            p(f'<rect x="{x}" y="{ly - 10}" width="22" height="10" fill="none" stroke="#666" stroke-dasharray="3,2"/>')
        p(f'<text x="{x + 28}" y="{ly}">{lab}</text>')
        x += 40 + 7 * len(lab)
    p('</svg>')
    return "\n".join(out)


def main():
    fld, steps, S = trace()
    assert S == [(0, 10), (26, 32)], S
    for st in steps:
        print("pop", NAMES[st["j"]], st["piece"], "->", [(NAMES[s], q) for s, q in st["adds"]])
    print("origin 0:", S)
    out = HERE / "figures" / "toy_backward_pass.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(svg(fld, steps, S))
    print("wrote", out)


if __name__ == "__main__":
    main()
