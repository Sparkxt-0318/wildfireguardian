"""Booth display: black background, white type, green live nodes, orange burned nodes."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

BG = "#000000"
FG = "#ffffff"
DIM = "#8a8a8a"
ROAD = "#3a3a3a"
HOUSE = "#262626"
LIVE = "#2ecc71"
BURNED = "#ff7a1a"
FRONT = "#ff9a3c"
# Arrival time: early burn in deep orange, later burn fading toward dark amber.
ARRIVAL_CMAP = LinearSegmentedColormap.from_list("arrival", ["#ff6a00", "#e0701c", "#6b3208"])


class Display:
    def __init__(self, fig, village, mode_label="SIMULATOR"):
        self.fig = fig
        self.v = village
        self.mode = mode_label
        fig.patch.set_facecolor(BG)
        self.ax = fig.add_axes([0.03, 0.08, 0.70, 0.80])
        self.side = fig.add_axes([0.76, 0.08, 0.22, 0.80])
        for a in (self.ax, self.side):
            a.set_facecolor(BG)
            a.set_xticks([])
            a.set_yticks([])
            for s in a.spines.values():
                s.set_visible(False)

    def draw(self, st, now, t_max=None):
        ax, side, v = self.ax, self.side, self.v
        ax.clear()
        side.clear()
        for a in (ax, side):
            a.set_facecolor(BG)
            a.set_xticks([])
            a.set_yticks([])
            for s in a.spines.values():
                s.set_visible(False)
        W, H = v["width_m"], v["height_m"]
        share, arr = st.fields()
        if np.isfinite(arr).any():
            vmax = t_max if t_max else max(np.nanmax(arr), 1.0)
            rgba = ARRIVAL_CMAP(np.clip(np.nan_to_num(arr, nan=0.0) / vmax, 0, 1))
            # Soft edge: opacity ramps up across the 0.5 burned-share boundary.
            support = np.clip((st.max_support_m - st.d_near) / 100.0, 0, 1)
            rgba[..., 3] = 0.75 * np.clip((share - 0.42) / 0.16, 0, 1) * support
            ax.imshow(rgba, origin="lower", extent=[0, W, 0, H], interpolation="bilinear", zorder=1)
            ax.contour(st.GX, st.GY, np.where(st.d_near <= st.max_support_m - 50, share, np.nan), levels=[0.5],
                       colors=[FRONT], linewidths=2.0, zorder=3)
        for r in v["roads"]:
            r = np.asarray(r)
            ax.plot(r[:, 0], r[:, 1], color=ROAD, lw=3.0, solid_capstyle="round", zorder=2)
        if v.get("houses"):
            h = np.asarray(v["houses"])
            ax.scatter(h[:, 0], h[:, 1], marker="s", s=60, c=HOUSE, lw=0, zorder=2)
        alive = ~st.dead & ~np.isnan(st.last)
        silent = np.isnan(st.last)
        ax.scatter(st.xy[alive, 0], st.xy[alive, 1], s=190, c=LIVE, edgecolors=BG, lw=1.5, zorder=5)
        ax.scatter(st.xy[st.dead, 0], st.xy[st.dead, 1], s=190, c=BURNED, edgecolors=BG, lw=1.5, zorder=5)
        ax.scatter(st.xy[silent, 0], st.xy[silent, 1], s=190, facecolors="none", edgecolors=DIM, lw=1.2, zorder=5)
        for i, (x, y) in zip(st.ids, st.xy):
            ax.text(x, y, str(i), color=BG, fontsize=7.5, ha="center", va="center", weight="bold", zorder=6)
        for s in st.spots:
            ax.scatter([s["x"]], [s["y"]], s=900, facecolors="none", edgecolors=FG, lw=1.8, zorder=7)
            ax.text(s["x"], s["y"] + 42, f"SPOT FIRE  {s['jump_m']:.0f} m jump", color=FG, fontsize=10,
                    ha="center", va="bottom", weight="bold", zorder=8)
        ax.set_xlim(-20, W + 20)
        ax.set_ylim(-20, H + 20)
        ax.set_aspect("equal")
        # Header.
        self.fig.texts.clear()
        self.fig.text(0.03, 0.94, "LAST GASP", color=FG, fontsize=22, weight="bold", ha="left", va="center")
        self.fig.text(0.03, 0.905, "Live fire front rebuilt from the moment each radio tag goes silent",
                      color=DIM, fontsize=11, ha="left", va="center")
        self.fig.text(0.98, 0.94, self.mode, color=DIM if self.mode == "SIMULATOR" else LIVE, fontsize=11,
                      ha="right", va="center", weight="bold")
        mm, ss = divmod(int(now), 60)
        n_live, n_dead = int(alive.sum()), int(st.dead.sum())
        self.fig.text(0.03, 0.04, f"{mm:02d}:{ss:02d}", color=FG, fontsize=14, weight="bold", ha="left", va="center")
        self.fig.text(0.11, 0.04, f"live {n_live}    burned {n_dead}    spot fires {len(st.spots)}",
                      color=FG, fontsize=12, ha="left", va="center")
        # Side panel: legend and recent events.
        y = 0.97
        for color, label, filled in ((LIVE, "live tag", True), (BURNED, "burned tag", True),
                                     (DIM, "not heard yet", False)):
            side.scatter([0.05], [y], s=120, c=color if filled else "none", edgecolors=color, lw=1.2,
                         transform=side.transAxes, clip_on=False)
            side.text(0.14, y, label, color=FG, fontsize=11, va="center", transform=side.transAxes)
            y -= 0.07
        side.plot([0.0, 0.1], [y, y], color=FRONT, lw=2.0, transform=side.transAxes, clip_on=False)
        side.text(0.14, y, "estimated fire front", color=FG, fontsize=11, va="center", transform=side.transAxes)
        y -= 0.07
        side.text(0.0, y, "shading: earlier burn is brighter", color=DIM, fontsize=9.5, va="center",
                  transform=side.transAxes)
        y -= 0.10
        side.text(0.0, y, "EVENTS", color=DIM, fontsize=10, weight="bold", va="center", transform=side.transAxes)
        y -= 0.06
        for t, msg in st.events[-9:][::-1]:
            m2, s2 = divmod(int(t), 60)
            side.text(0.0, y, f"{m2:02d}:{s2:02d}  {msg}", color=FG, fontsize=10, va="center",
                      transform=side.transAxes)
            y -= 0.055
        side.set_xlim(0, 1)
        side.set_ylim(0, 1)
