"""F07 forward against backward: one schematic network, two panels.

Slide 7, full slide. Left "Before": grey arrows search forward from one village (one search per village and per
departure time). Right "Now": blue arrows flow backward from the two shelters over the whole network, and four
roads carry a small time bar showing when that road can still lead to safety (teal), with a gap on one.

The network is a clean synthetic one of 25 junctions (DECISIONS.md D7): the real Uiseong–Andong graph has 23,158
nodes and is unreadable at this scale. The time bars are illustrative shapes and carry no numbers.
"""
from collections import deque

import numpy as np

import style as S
from figkit import save
from prov import Ledger
from scene import Scene

NR, NC = 5, 5
REMOVE = {((0, 1), (0, 2)), ((1, 2), (2, 2)), ((2, 3), (3, 3)), ((3, 0), (3, 1)), ((4, 2), (4, 3)),
          ((1, 0), (2, 0)), ((3, 2), (4, 2)), ((0, 3), (1, 3))}
DIAG = [((0, 0), (1, 1)), ((2, 2), (3, 3)), ((1, 3), (2, 4)), ((3, 1), (4, 0)), ((2, 1), (3, 2))]
VILLAGE = (2, 1)
SHELTERS = [(0, 4), (4, 4)]


def network():
    rng = np.random.RandomState(7)
    pos = {}
    for r in range(NR):
        for c in range(NC):
            pos[(r, c)] = (c + rng.uniform(-0.18, 0.18), r + rng.uniform(-0.16, 0.16))
    edges = []
    for r in range(NR):
        for c in range(NC):
            for dr, dc in ((0, 1), (1, 0)):
                a, b = (r, c), (r + dr, c + dc)
                if b[0] < NR and b[1] < NC and (a, b) not in REMOVE:
                    edges.append((a, b))
    edges += DIAG
    adj = {n: [] for n in pos}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    return pos, edges, adj


def bfs(adj, sources):
    depth, parent = {}, {}
    q = deque()
    for s in sources:
        depth[s] = 0
        q.append(s)
    while q:
        u = q.popleft()
        for v in sorted(adj[u]):
            if v not in depth:
                depth[v] = depth[u] + 1
                parent[v] = u
                q.append(v)
    return depth, parent


def panel(sc, pos, edges, adj, ox, oy, sx, sy, tag, mode):
    P = lambda n: (ox + pos[n][0] * sx, oy + pos[n][1] * sy)  # noqa: E731
    for a, b in edges:
        sc.line([P(a), P(b)], color=S.LIGHT, lw=3.0, name=f"{tag} road {a}-{b}", group=f"{tag} roads", role="mark")
    for n in pos:
        if n != VILLAGE and n not in SHELTERS:
            x, y = P(n)
            sc.circle(x, y, 0.05, fill=S.MID, name=f"{tag} junction {n}", group=f"{tag} roads", role="mark")
    if mode == "forward":
        depth, parent = bfs(adj, [VILLAGE])
        # the search fans out three steps, and one branch continues until it meets a shelter
        target = min(SHELTERS, key=lambda s: depth[s])
        path, n = set(), target
        while n in parent:
            path.add((parent[n], n))
            n = parent[n]
        for v, u in parent.items():
            if depth[v] <= 3 or (u, v) in path:
                a = 0.2 if u == VILLAGE else 0.12
                sc.line(_shorten(P(u), P(v), a=a), color=S.MID, lw=2.2, arrow=True, head=0.13,
                        name=f"{tag} search {u}->{v}", group=f"{tag} forward search", role="mark")
    else:
        depth, parent = bfs(adj, SHELTERS)
        for v, u in parent.items():
            sc.line(_shorten(P(u), P(v)), color=S.OURS, lw=2.2, arrow=True, head=0.13,
                    name=f"{tag} backward {u}->{v}", group=f"{tag} backward pass", role="mark")
    for i, s in enumerate(SHELTERS):
        x, y = P(s)
        sc.rect(x - 0.13, y - 0.13, 0.26, 0.26, fill=S.SAFE, name=f"{tag} shelter {i + 1}",
                group=f"{tag} shelter {i + 1}", role="mark")
    x, y = P(VILLAGE)
    if mode == "forward":
        sc.circle(x, y, 0.15, fill=S.INK, name=f"{tag} village", group=f"{tag} village", role="mark")
    else:
        sc.circle(x, y, 0.07, fill=S.MID, name=f"{tag} village", group=f"{tag} village", role="mark")
    return P


def _shorten(p, q, a=0.12, b=0.10):
    v = np.subtract(q, p)
    L = np.hypot(*v)
    u = v / L
    return [tuple(np.add(p, u * a)), tuple(np.subtract(q, u * b))]


def time_bar(sc, x, y, segs, name):
    """A track of 0.9 in with teal segments where the road still leads to a shelter."""
    w, h = 0.9, 0.12
    sc.rect(x, y, w, h, fill=S.WHITE, edge=S.MID, lw=0.8, name=f"{name} track", group=name, role="mark")
    for i, (a, b) in enumerate(segs):
        sc.rect(x + a * w, y, (b - a) * w, h, fill=S.SAFE, name=f"{name} safe window {i + 1}", group=name, role="mark")


def build():
    pos, edges, adj = network()
    sc = Scene("F07_forward_backward")
    sx, sy = 1.22, 0.95
    oyL = 1.99
    PL = panel(sc, pos, edges, adj, 0.85, oyL, sx, sy, "Before", "forward")
    PR = panel(sc, pos, edges, adj, 7.35, oyL, sx, sy, "Now", "backward")
    # headers
    sc.text(0.45, 0.55, "Before", size=28, bold=True, name="Before header", group="Before labels")
    sc.text(0.45, 1.17, "Forward from one village", size=S.PT_BODY, color=S.MID, name="Before subheader",
            group="Before labels")
    sc.text(6.95, 0.55, "Now", size=28, bold=True, color=S.OURS, name="Now header", group="Now labels")
    sc.text(6.95, 1.17, "Backward from the shelters, over every road at once", size=S.PT_BODY, color=S.MID,
            name="Now subheader", group="Now labels")
    # divider
    sc.line([(6.67, 0.45), (6.67, 7.1)], color=S.LIGHT, lw=1.0, name="divider", group="divider", role="bg")
    # labels for village and shelters
    for P, tag in ((PL, "Before"), (PR, "Now")):
        x, y = P(SHELTERS[0])
        sc.text(x + 0.22, y - 0.30, "shelter", color=S.SAFE, bold=True, name=f"{tag} shelter label 1",
                group=f"{tag} labels")
        x, y = P(SHELTERS[1])
        sc.text(x + 0.22, y + 0.30, "shelter", color=S.SAFE, bold=True, name=f"{tag} shelter label 2",
                group=f"{tag} labels")
    x, y = PL(VILLAGE)
    sc.text(x - 0.62, y - 0.40, "village", bold=True, ha="center", name="Before village label", group="Before labels")
    # counter, bottom left
    sc.rect(0.45, 6.55, 5.85, 0.62, fill=S.WHITE, edge=S.MID, lw=1.0, name="counter box", group="counter", role="box")
    sc.text(0.70, 6.86, "one search per village and per departure time", size=S.PT_BODY, name="counter text",
            group="counter")
    # time bars on four roads in the right panel, placed in the faces next to the road
    bars = [
        (((0, 2), (0, 3)), [(0.0, 0.62)], -1),
        (((2, 1), (2, 2)), [(0.0, 0.30), (0.55, 0.85)], -1),
        (((4, 1), (4, 2)), [(0.0, 0.45)], +1),
        (((3, 3), (3, 4)), [(0.0, 0.78)], -1),
    ]
    for i, ((a, b), segs, side) in enumerate(bars):
        (x0, y0), (x1, y1) = PR(a), PR(b)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        time_bar(sc, mx - 0.45, my + (0.13 if side > 0 else -0.25), segs, f"time bar {i + 1}")
    # key for the time bars, bottom right
    kx, ky = 7.15, 6.56
    time_bar(sc, kx, ky + 0.05, [(0.0, 0.30), (0.55, 0.85)], "time bar key")
    sc.line([(kx, ky + 0.60), (kx + 0.9, ky + 0.60)], color=S.INK, lw=1.0, arrow=True, head=0.08,
            name="time bar key axis", group="time bar key", role="mark")
    sc.text(kx + 1.15, ky + 0.11, "when this road still leads to a shelter",
            size=S.PT_MIN, name="time bar key text", group="time bar key")
    sc.text(kx + 1.15, ky + 0.60, "departure time", size=S.PT_MIN, color=S.MID, name="time bar key time",
            group="time bar key")
    return sc


def main():
    L = Ledger("F07", "Forward against backward (schematic)")
    L.note("Schematic on a synthetic 25-junction network; no number is shown. The time bars are illustrative shapes.")
    L.save()
    sc = build()
    fig = S.new_figure()
    sc.draw(fig)
    sc.save_spec(fig)
    save(fig, "F07_forward_backward", kind="scene")


if __name__ == "__main__":
    main()
