#!/usr/bin/env python
"""Disclose how unequal the LOGO-CV folds are. Disclosure, not re-analysis.

Session 10 follow-up, task 4. Mean-of-folds gives every fold one vote.
``gangneung_2023`` carries 396 of 151,904 rows and 8 of 2,989 positive cells —
about a quarter of one percent of the evidence — and casts one sixth of that
vote, while also supplying much of the reported fold spread. Nothing about that
is hidden in the pipeline; it simply was never written down in one place.

**No metric is recomputed here.** Fold AUCs are COPIED from the committed
artifact ``data/processed/spread_v2_lofo.json``. The only things computed are
counts — rows, positive cells, overpasses — which are properties of the dataset,
not estimates derived from it.

    python scripts/fold_sizes.py --write     # docs/fold_sizes.json + a table

Writes under docs/, not data/processed/, so the disclosure is tracked without
joining the Korean baseline's artifact set.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

LOFO = REPO / "data" / "processed" / "spread_v2_lofo.json"
OUT_JSON = REPO / "docs" / "fold_sizes.json"
OUT_MD = REPO / "docs" / "fold_sizes.md"


def collect() -> dict:
    from wildfireguardian.spread_v2 import data as datamod
    from wildfireguardian.spread_v2 import grid as gridmod
    from wildfireguardian.spread_v2.features import build_dataset

    committed = json.loads(LOFO.read_text(encoding="utf-8"))
    fires = sorted(committed["per_fire_auc"])

    ds = build_dataset(fires)
    rows = []
    for fid in fires:
        sub = ds[ds["fire_id"] == fid]
        ev = datamod.load_event(fid)
        g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=gridmod.DEFAULT_CELL_M)
        snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=90.0)
        rows.append({
            "fire_id": fid,
            "rows": int(len(sub)),
            "positive_cells": int(sub["label"].sum()),
            "n_overpasses": int(len(snaps)),
            "n_transitions": max(0, int(len(snaps)) - 1),
            "fold_auc_committed": committed["per_fire_auc"][fid],
            "share_of_rows": round(float(len(sub)) / committed["n_rows"], 6),
            "share_of_positives": round(
                float(sub["label"].sum()) / committed["n_positives"], 6),
            "vote_in_mean_of_folds": round(1.0 / len(fires), 6),
        })

    rows.sort(key=lambda r: r["rows"])
    total_rows = sum(r["rows"] for r in rows)
    total_pos = sum(r["positive_cells"] for r in rows)
    return {
        "schema_version": 1,
        "title": "LOGO-CV fold sizes — disclosure of fold-weight heterogeneity",
        "provenance": "derived (counts) + copied (fold AUCs)",
        "arm": "A_disclosure",
        "generated_by": "scripts/fold_sizes.py",
        "fold_auc_source": "data/processed/spread_v2_lofo.json :: per_fire_auc "
                           "(COPIED, not recomputed)",
        "n_folds": len(rows),
        "n_rows_total": total_rows,
        "n_positives_total": total_pos,
        "matches_committed_shape": (total_rows == committed["n_rows"]
                                    and total_pos == committed["n_positives"]),
        "largest_over_smallest_rows": round(
            rows[-1]["rows"] / max(1, rows[0]["rows"]), 1),
        "folds": rows,
        "reading": (
            "Every fold casts an equal vote in mean-of-folds while carrying "
            "wildly unequal evidence. Pooled AUC is the primary metric because "
            "it weights each row once. Mean-of-folds must always be reported "
            "with this table beside it."
        ),
    }


def to_markdown(payload: dict) -> str:
    lines = [
        "# LOGO-CV 폴드 크기 — 폴드 가중 불균형 공시",
        "",
        "`scripts/fold_sizes.py` 로 생성됩니다. **폴드 AUC 는 커밋된 아티팩트",
        "(`data/processed/spread_v2_lofo.json :: per_fire_auc`) 에서 그대로",
        "복사한 값이며 재계산하지 않았습니다.** 계산한 것은 개수(행·양성 셀·",
        "오버패스)뿐이고, 이는 데이터셋의 성질이지 추정치가 아닙니다.",
        "",
        "| 화재 | 행 | 양성 셀 | 오버패스 | 전이 | 행 비중 | 양성 비중 | mean-of-folds 지분 | 폴드 AUC (커밋본) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in payload["folds"]:
        lines.append(
            f"| `{r['fire_id']}` | {r['rows']:,} | {r['positive_cells']:,} | "
            f"{r['n_overpasses']} | {r['n_transitions']} | "
            f"{r['share_of_rows']*100:.2f}% | {r['share_of_positives']*100:.2f}% | "
            f"{r['vote_in_mean_of_folds']*100:.1f}% | {r['fold_auc_committed']:.4f} |")
    lines += [
        f"| **합계** | **{payload['n_rows_total']:,}** | "
        f"**{payload['n_positives_total']:,}** | | | 100% | 100% | 100% | |",
        "",
        "## 읽는 법",
        "",
        f"최대 폴드는 최소 폴드보다 행이 **{payload['largest_over_smallest_rows']:.0f}배** "
        "많습니다. 그런데 mean-of-folds 에서 두 폴드의 지분은 같습니다.",
        "",
        "- **Pooled AUC 가 1차 지표입니다.** 각 행을 정확히 한 번씩 가중합니다.",
        "- **Mean-of-folds 는 반드시 이 표와 함께 제시합니다.** 단독으로 쓰면",
        "  증거의 0.26% 를 담은 폴드가 값의 6분의 1과 산포의 상당 부분을",
        "  결정한다는 사실이 보이지 않습니다.",
        "- 순열 중요도는 이와 달리 **행 가중** 평균이므로 이 불균형의 영향을",
        "  받지 않습니다 (`spread_v2/model.py::leave_one_fire_out`).",
        "",
        "_공시이며 재분석이 아닙니다. 어떤 값도 재계산·재가중하지 않았습니다._",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    payload = collect()
    if not payload["matches_committed_shape"]:
        raise SystemExit("per-fold counts do not sum to the committed shape — stop")
    if args.write:
        OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        OUT_MD.write_text(to_markdown(payload), encoding="utf-8")
        print(f"wrote {OUT_JSON.relative_to(REPO)} and {OUT_MD.relative_to(REPO)}")
    for r in payload["folds"]:
        print(f"  {r['fire_id']:24s} rows={r['rows']:>7,} pos={r['positive_cells']:>5,} "
              f"ops={r['n_overpasses']:>3} share={r['share_of_rows']*100:5.2f}% "
              f"auc={r['fold_auc_committed']:.4f}")
    print(f"  largest/smallest rows = {payload['largest_over_smallest_rows']}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
