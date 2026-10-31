"""The Track A leaderboard: pool ``firecast-lab run`` rows and score every METRICS.md metric (METRICS.md section 8).

Rows hold additive per-window terms (``harness.TERM_COLUMNS``). A *table* is one country, split, lead, scoring
domain and K, real or SYNTHETIC: never pooled across these. An *entry* of a table is one run (baseline, coupling,
copula length, seed). An entry pools its rows by summing their terms and reports each metric with a whole-fire
percentile bootstrap interval (``metrics.fire_bootstrap``): every draw resamples whole fires and pools their window
terms. The entries of a table share their fires, so they share the draws.

Refusals (``LeaderboardError``, a ValueError):

- entries of one table that scored different windows, or different cells in the same window (``mask_sha256``):
  their scores are not comparable (review finding A-m5);
- an entry with two rows for one window, rows without the per-window terms, or rows whose term definitions differ;
- SYNTHETIC rows without an explicit output path (``cli``): firecast-lab/LEADERBOARD.md holds real-data rows only.

    firecast-lab leaderboard [--results DIR] [--out PATH]
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from firecast_lab import harness
from firecast_lab import metrics as m

INTS = ("n_cells", "positives", "removed_by_support", "zero_prob_positives", "rank_fully_tied", "members", "lead_h")
FLOATS = ("brier_sum", "brier_prob_sum", "brier_persistence_sum", "brier_reference_sum", "crps_sum", "crps_fair_sum",
          "spread_var_sum", "spread_err2_sum", *harness.FSS_COLUMNS)
FLAGS = ("in_sample", "synthetic")
LEVEL = 0.95


class LeaderboardError(ValueError):
    """Rows that cannot be pooled or compared honestly."""


# --------------------------------------------------------------------------------------------- reading rows
def _flag(value) -> bool:
    return value if isinstance(value, bool) else str(value) == "True"


def parse_row(raw: dict, source: str = "") -> dict:
    """A run row with typed values: numbers, flags, JSON lists and the config. Works on CSV rows (strings) and on
    ``harness.run`` rows (numbers and JSON strings)."""
    missing = [c for c in harness.TERM_COLUMNS if c not in raw]
    if missing:
        raise LeaderboardError(f"{source or 'a row'} has no per-window terms ({missing[0]}, ...): it was written "
                               "before they existed; rerun `firecast-lab run`")
    row = dict(raw, source=source)
    for c in INTS:
        row[c] = int(raw[c])
    for c in FLOATS:
        row[c] = float(raw[c])
    for c in FLAGS:
        row[c] = _flag(raw[c])
    for c in harness.LIST_COLUMNS:
        row[c] = json.loads(raw[c]) if isinstance(raw[c], str) else list(raw[c])
    length = raw.get("length_cells")
    row["length_cells"] = None if length in (None, "") else float(length)
    config = raw.get("config") or {}
    row["config"] = json.loads(config) if isinstance(config, str) else dict(config)
    return row


def read_rows(results) -> tuple[list[dict], list[str]]:
    """Run rows of every CSV in ``results`` (typed by ``parse_row``) and the names of the CSVs that are not run files
    (decision rows, timings). Rows written before the per-window terms existed are refused."""
    folder = Path(results)
    rows, other = [], []
    for path in sorted(folder.glob("*.csv")) if folder.is_dir() else []:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if not {"baseline", "mask_sha256"} <= set(reader.fieldnames or ()):
                other.append(path.name)
                continue
            rows += [parse_row(r, path.name) for r in reader]
    return rows, other


# ------------------------------------------------------------------------------------------------- grouping
def table_key(row: dict) -> tuple:
    return (row["synthetic"], row["country"], row["split"], row["lead_h"], row["config"].get("domain", "headline"),
            row["members"])


def entry_key(row: dict) -> tuple:
    return row["baseline"], row["coupling"], row["length_cells"], str(row.get("seed", ""))


def tables(rows: list[dict]) -> dict[tuple, dict[tuple, list[dict]]]:
    """``{table key: {entry key: rows}}`` after the comparability checks (module doc)."""
    grouped: dict[tuple, dict[tuple, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        grouped[table_key(r)][entry_key(r)].append(r)
    for key, entries in grouped.items():
        name = _table_title(key)
        definitions = {json.dumps(r["config"].get("terms"), sort_keys=True) for es in entries.values() for r in es
                       if r["config"].get("terms") is not None}
        if len(definitions) > 1:
            raise LeaderboardError(f"{name}: rows use different term definitions (bins, sizes): rerun them alike")
        masks: dict[tuple, dict[tuple, str]] = defaultdict(dict)
        for entry, es in entries.items():
            for r in es:
                window = (r["fire"], r["cutoff_utc"])
                if window in masks and entry in masks[window]:
                    raise LeaderboardError(f"{name}: {_entry_name(entry)} has two rows for {window}")
                masks[window][entry] = r["mask_sha256"]
        for window, by_entry in sorted(masks.items()):
            absent = sorted(_entry_name(e) for e in entries if e not in by_entry)
            if absent:
                raise LeaderboardError(f"{name}: entries scored different windows ({', '.join(absent)} lack {window}); "
                                       "compare runs on identical windows only")
            if len(set(by_entry.values())) > 1:
                detail = ", ".join(f"{_entry_name(e)}: {h}" for e, h in sorted(by_entry.items()))
                raise LeaderboardError(f"{name}: refusing to compare runs that scored different cells in window "
                                       f"{window} (mask_sha256 {detail}); score every baseline on identical cells")
    return {k: dict(v) for k, v in grouped.items()}


# ------------------------------------------------------------------------------------------------- metrics
def _stack(rows, *columns) -> np.ndarray:
    """``[windows, terms]``: scalar columns, and list columns spread out in order."""
    out = []
    for r in rows:
        line = []
        for c in columns:
            line += list(r[c]) if c in harness.LIST_COLUMNS else [r[c]]
        out.append(line)
    return np.asarray(out, dtype=np.float64)


def _ratio(s):
    return s[..., 0] / s[..., 1]


def _skill(s):
    return 1.0 - s[..., 0] / s[..., 1]


def _number(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _bootstrap(fire, terms, statistic, draws: int, seed: int) -> dict:
    """A metric's point value and whole-fire interval; None when its terms are not finite (e.g. K < 2) or it is
    undefined on the pooled sums."""
    if terms.size == 0 or not np.isfinite(terms).all():
        return dict(point=None, interval=[None, None], undefined_draws=None)
    out = m.fire_bootstrap(fire, terms, statistic, draws=draws, seed=seed, level=LEVEL)
    point = _number(out["point"])
    return dict(point=point, interval=[_number(v) for v in out["interval"]] if point is not None else [None, None],
                undefined_draws=out["undefined_draws"])


def score_entry(rows: list[dict], *, draws: int = 10000, seed: int = m.BOOTSTRAP_SEED) -> dict:
    """Every METRICS.md metric of one entry from its pooled window terms, with whole-fire intervals; plus the pooled
    reliability rows, spread-skill rows and rank histogram (point values)."""
    K = rows[0]["members"]
    fire = np.array([r["fire"] for r in rows])
    rel, levels, ranks = len(m.RELIABILITY_EDGES), K + 1, K + 1

    def boot(columns, statistic):
        return _bootstrap(fire, _stack(rows, *columns), statistic, draws, seed)

    metrics = dict(
        brier=boot(("brier_sum", "n_cells"), _ratio),
        bss_vs_persistence=boot(("brier_sum", "brier_persistence_sum"), _skill),
        bss_vs_calibrated_dilation=boot(("brier_sum", "brier_reference_sum"), _skill),
        brier_probability_field=boot(("brier_prob_sum", "n_cells"), _ratio),
        ece=boot(("rel_count", "rel_forecast_sum", "rel_observed_sum"),
                 lambda s: m.ece_from_sums(s[..., :rel], s[..., rel:2 * rel], s[..., 2 * rel:])),
        average_precision=boot(("pr_cells", "pr_positives"),
                               lambda s: m.average_precision_from_counts(s[..., :levels], s[..., levels:])),
        base_rate=boot(("positives", "n_cells"), _ratio),
        **{f"fss_{n}": boot((f"fss_num_{n}", f"fss_den_{n}"), _skill) for n in m.FSS_SIZES},
        crps_h=boot(("crps_sum", "n_cells"), _ratio),
        crps_fair_h=boot(("crps_fair_sum", "n_cells"), _ratio),
        spread_skill=boot(("spread_var_sum", "spread_err2_sum"),
                          lambda s: m.spread_skill_from_sums(K, s[..., 0], s[..., 1])),
        rank_outer_share=boot(("rank_counts",), lambda s: (s[..., 0] + s[..., ranks - 1]) / s.sum(axis=-1)))
    total = _stack(rows, "rel_count", "rel_forecast_sum", "rel_observed_sum").sum(axis=0)
    spread = (_stack(rows, "spread_row_cells", "spread_row_var_sum", "spread_row_err2_sum").sum(axis=0)
              if K > 1 else np.zeros(0))
    n_rows = len(m.SPREAD_SD_EDGES_H) + 2
    spread_rows = [m.spread_row(K, int(spread[i]), spread[n_rows + i], spread[2 * n_rows + i], lower=lo, upper=hi)
                   for i, (lo, hi) in enumerate(m.spread_row_bounds())] if spread.size else []
    return dict(
        name=_entry_name(entry_key(rows[0])), baseline=rows[0]["baseline"], coupling=rows[0]["coupling"],
        length_cells=rows[0]["length_cells"], seed=rows[0].get("seed"), members=K,
        in_sample=any(r["in_sample"] for r in rows), synthetic=any(r["synthetic"] for r in rows),
        windows=len(rows), fires=int(np.unique(fire).size), cells=int(sum(r["n_cells"] for r in rows)),
        positives=int(sum(r["positives"] for r in rows)),
        zero_prob_positives=int(sum(r["zero_prob_positives"] for r in rows)),
        removed_by_support=int(sum(r["removed_by_support"] for r in rows)),
        commits=sorted({str(r.get("commit") or "") for r in rows}), metrics=metrics,
        fss_useful=m.fss_useful(sum(r["positives"] for r in rows) / max(1, sum(r["n_cells"] for r in rows))),
        reliability=m.reliability_from_sums(total[:rel], total[rel:2 * rel], total[2 * rel:]),
        spread_rows=spread_rows, rank_counts=_stack(rows, "rank_counts").sum(axis=0).astype(int).tolist(),
        rank_expected_outer_share=2.0 / (K + 1), rank_fully_tied=int(sum(r["rank_fully_tied"] for r in rows)))


def build(rows: list[dict], *, draws: int = 10000, seed: int = m.BOOTSTRAP_SEED) -> dict:
    """The leaderboard: per table (``tables``), every entry's ``score_entry``."""
    if not rows:
        raise LeaderboardError("no `firecast-lab run` rows to pool")
    out = []
    for key, entries in sorted(tables(rows).items(), key=lambda kv: [str(v) for v in kv[0]]):
        scored = [score_entry(es, draws=draws, seed=seed) for _, es in sorted(entries.items(), key=lambda kv:
                                                                               [str(v) for v in kv[0]])]
        synthetic, country, split, lead, domain, members = key
        windows = sorted({(r["fire"], r["cutoff_utc"]) for es in entries.values() for r in es})
        out.append(dict(title=_table_title(key), synthetic=synthetic, country=country, split=split, lead_h=lead,
                        domain=domain, members=members, windows=len(windows),
                        fires=len({f for f, _ in windows}), entries=scored))
    return dict(generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                synthetic=any(t["synthetic"] for t in out), draws=draws, seed=seed, level=LEVEL,
                rows=len(rows), sources=sorted({r["source"] for r in rows if r.get("source")}), tables=out)


# ------------------------------------------------------------------------------------------------ rendering
def _entry_name(entry: tuple) -> str:
    baseline, coupling, length, seed = entry
    name = f"{baseline}, {coupling}" + (f" L = {length:g}" if length is not None else "")
    return name + (f", seed {seed}" if seed not in ("", "0", "None") else "")


def _table_title(key: tuple) -> str:
    synthetic, country, split, lead, domain, members = key
    return (("SYNTHETIC - " if synthetic else "") + f"{country}, {split}, lead {lead} h, {domain} domain, K = {members}")


def _fmt(value, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}g}"


def _cell(metric: dict, digits: int = 4) -> str:
    if metric["point"] is None:
        return "n/a"
    lo, hi = metric["interval"]
    return f"{_fmt(metric['point'], digits)} [{_fmt(lo, digits)}, {_fmt(hi, digits)}]"


def render(board: dict) -> str:
    """The leaderboard as markdown (SYNTHETIC tables and the title say so)."""
    head = "SYNTHETIC - " if board["synthetic"] else ""
    lines = [f"# {head}Track A leaderboard", "",
             f"Generated by `firecast-lab leaderboard` on {board['generated_utc']} from {board['rows']} rows "
             f"({', '.join(board['sources']) or 'in memory'}). Definitions: `METRICS.md`; pooling: METRICS.md §8.",
             f"Intervals: {board['level']:.0%} whole-fire percentile bootstrap ({board['draws']:,} draws, seed "
             f"{board['seed']}); windows are not independent fires, and few fires give coarse intervals.", ""]
    if board["synthetic"]:
        lines += ["**SYNTHETIC rows: plumbing only, not a result about any real fire.**", ""]
    for t in board["tables"]:
        lines += [f"## {t['title']}", "",
                  f"{t['windows']} windows on {t['fires']} fires; every entry scored the same windows and cells "
                  "(mask_sha256 checked).", ""]
        entries = t["entries"]
        names = [e["name"] + (" (in-sample)" if e["in_sample"] else "") for e in entries]
        lines += ["| entry | fires | windows | cells | Brier | BSS vs persistence | BSS vs calibrated dilation | ECE "
                  "| AP (base rate) | zero-p positives | removed by support |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, e in zip(names, entries):
            x = e["metrics"]
            lines.append(f"| {name} | {e['fires']} | {e['windows']} | {e['cells']:,} | {_cell(x['brier'])} | "
                         f"{_cell(x['bss_vs_persistence'], 3)} | {_cell(x['bss_vs_calibrated_dilation'], 3)} | "
                         f"{_cell(x['ece'])} | {_cell(x['average_precision'], 3)} ({_fmt(x['base_rate']['point'], 3)})"
                         f" | {e['zero_prob_positives']:,} | {e['removed_by_support']:,} |")
        lines += ["", "| entry | CRPS (h) | fair CRPS (h) | spread/skill | rank outer share (flat: "
                  f"{_fmt(entries[0]['rank_expected_outer_share'], 3)}) | fully tied cells |", "|---|---|---|---|---|---|"]
        for name, e in zip(names, entries):
            x = e["metrics"]
            lines.append(f"| {name} | {_cell(x['crps_h'])} | {_cell(x['crps_fair_h'])} | {_cell(x['spread_skill'], 3)} "
                         f"| {_cell(x['rank_outer_share'], 3)} | {e['rank_fully_tied']:,} |")
        sizes = " | ".join(f"n = {n}" for n in m.FSS_SIZES)
        lines += ["", f"Fractions Skill Score (aggregate; useful above 0.5 + f0 / 2 = "
                      f"{_fmt(entries[0]['fss_useful'], 3)}):", "", f"| entry | {sizes} |",
                  "|---|" + "---|" * len(m.FSS_SIZES)]
        for name, e in zip(names, entries):
            lines.append(f"| {name} | " + " | ".join(_cell(e["metrics"][f"fss_{n}"], 3) for n in m.FSS_SIZES) + " |")
        lines += ["", "Reliability (pooled): mean forecast / observed frequency (cells).", "",
                  "| p | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for i, row in enumerate(entries[0]["reliability"]):
            label = "0" if i == 0 else (("(" if i == 1 else "[") + f"{row['lower']:g}, {row['upper']:g}"
                                        + ("]" if row["upper"] == 1 else ")"))
            cells = [e["reliability"][i] for e in entries]
            lines.append(f"| {label} | " + " | ".join(
                "-" if not c["count"] else f"{c['mean_forecast']:.3g} / {c['observed_frequency']:.3g} ({c['count']:,})"
                for c in cells) + " |")
        if all(e["spread_rows"] for e in entries):
            lines += ["", "Spread-skill by member sd of the arrival hour (fixed rows): ratio (cells).", "",
                      "| member sd (h) | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
            for i, row in enumerate(entries[0]["spread_rows"]):
                label = "0" if i == 0 else ("(" if i == 1 else "[") + f"{row['lower']:g}, {row['upper']:g})"
                cells = [e["spread_rows"][i] for e in entries]
                lines.append(f"| {label} | " + " | ".join(
                    "-" if not c["cells"] else f"{_fmt(c['ratio'], 3)} ({c['cells']:,})" for c in cells) + " |")
        lines.append("")
    return "\n".join(lines)


def write(board: dict, out) -> Path:
    """The markdown at ``out`` and the full leaderboard (pooled rows, histograms) as JSON next to it."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(board))
    out.with_suffix(".json").write_text(json.dumps(board, indent=1, default=str) + "\n")
    return out
