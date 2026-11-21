"""Certificates: one shared instance (masks + the cell closures and geometry they come from) and one JSON per village,
re-checkable with verifier/verify_certificate.py and the kcf-theorem checker.py alone."""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path

from . import fmt
from .report import safe_id

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "vendor/kcf_theorem/checker.py"
VERIFIER = HERE / "verifier/verify_certificate.py"


def _dump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def instance_bytes(road, inst, close_s, H, dwell, heat=None, open_s=None) -> bytes:
    doc = {
        "schema": "wfg.roadlayer.instance/1",
        "H": H, "dwell_s": dwell, "grid": road.grid_json, "crs": road.crs, "graph_revision": road.revision,
        "n_nodes": inst.n_nodes,
        "edges": [[t, h, d] for t, h, d in zip(inst.tail, inst.head, inst.D)],
        "source_way": road.source_way,
        "segments": road.seg_raw,
        "node_cell": road.node_cell,
        "waitable": [v for v, w in enumerate(inst.waitable) if w],
        "forbidden": sorted([a, b] for a, b in inst.forbidden),
        "cell_closure_s": {str(c): s for c, s in sorted(close_s.items())},
        "B": {str(j): [list(p) for p in b] for j, b in enumerate(inst.B) if b},
        "W": {str(v): [list(p) for p in w] for v, w in enumerate(inst.W) if w},
        "rules": {
            "edge": "B_j = [max(0, ceil(b - D_j * z_end)) minimised over segments (cell, z_end) with closure b, H]",
            "wait": "W_v = [max(b - 1, 0), H] for a waitable node in a cell closing at b",
            "shelter": "A = [0, H - dwell], ending at b - dwell - 1 if the shelter cell closes at b",
            "origin": "IB = [b, H] if the origin cell closes at b",
            "source": "research/kcf-replay/replay.py Region.instance / Region.accept / run_one",
        },
    }
    if open_s:
        # reopening option (research/kcf-reopen): the cell is closed on [b, r) with r = cell_reopen_s
        doc["cell_reopen_s"] = {str(c): int(r) for c, r in sorted(open_s.items())}
        doc["rules"]["reopen"] = ("reopening on: a cell with closure b and reopening r is closed on [b, r); B_j = union over "
                                  "segments of [max(0, ceil(b - D_j z_end)), ceil(r - D_j z_start) - 1], W_v = [max(b - 1, 0), "
                                  "r - 1], A = [0, H - dwell] minus [b - dwell, r - 1], IB = [b, r - 1]; cells without r as above. "
                                  "Feasible sets are no longer prefixes (THEOREM.md Theorem 1 applies, Theorem 2 does not)")
    if heat is not None:
        # heat option: closure second per road piece (edge, piece index) and per node, from the radiant-heat rule
        # (research/kcf-radiation); the masks above follow from these, not from cell_closure_s.
        pieces = {}
        for j, k, b in zip(heat.P["edge"].tolist(), heat.P["k"].tolist(), heat.piece_close.tolist()):
            if b != float("inf") and b <= H:
                pieces.setdefault(str(j), []).append([k, int(b)])
        doc["heat_piece_closure_s"] = pieces
        doc["heat_node_closure_s"] = {str(v): int(b) for v, b in enumerate(heat.node_close.tolist())
                                      if b != float("inf") and b <= H}
        doc["rules"]["heat"] = ("heat option on: B uses the per-piece closure b of each segment (same formula), W, A "
                                "and IB the per-node closure; fire arrival at a village stays the cell closure")
    return _dump(doc)


def write_instance(cdir: Path, raw: bytes) -> str:
    cdir.mkdir(parents=True, exist_ok=True)
    with open(cdir / "instance.json.gz", "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0, compresslevel=6, filename="") as g:
            g.write(raw)
    shutil.copyfile(CHECKER, cdir / "checker.py")
    shutil.copyfile(VERIFIER, cdir / "verify_certificate.py")
    return hashlib.sha256(raw).hexdigest()


def village_doc(row, ctx, inst_sha) -> dict:
    o = row["origin"]
    road = ctx["road"]
    H = ctx["horizon_s"]
    on = o["node"]
    shelters = [{"rank": p["k"], "id": p["shelter"]["id"], "name": p["shelter"]["name"], "node": p["shelter"]["node"],
                 "node_id": p["shelter"]["entry_node_id"], "A": [list(x) for x in p["accept"]],
                 "claimed_feasible": [list(x) for x in p["set"]], "claimed_latest": p["L"],
                 "fire_free_latest": p["fire_free_latest"]} for p in row["per_shelter"]]
    wit = []
    if row["last"] is not None:
        p = row["last"]
        wit.append({"what": "latest", "shelter_rank": p["k"], "departure": p["L"], "arrival": p["w_last"]["arrival"],
                    "legs": p["w_last"]["legs"]})
    if row["now"] is not None:
        p = row["now"]
        wit.append({"what": "issue_time", "shelter_rank": p["k"], "departure": 0, "arrival": p["w_first"]["arrival"],
                    "legs": p["w_first"]["legs"]})
    cut = row["cut"]
    kind = "at_issue" if cut == 0 else ("horizon" if cut is None else "fire")
    st = ctx["settings"]["stage"]
    return {
        "schema": "wfg.roadlayer.certificate/1",
        "notice": {"ko": fmt.NOTICE_LONG["ko"], "en": fmt.NOTICE_LONG["en"]},
        "instance": {"file": "../instance.json.gz", "sha256_uncompressed": inst_sha},
        "issue_time_utc": ctx["issue"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "horizon_s": H, "dwell_s": ctx["settings"]["routing"]["dwell_s"],
        "village": {"id": o["id"], "name": o["name"], "sigungu": o["sigungu"], "eupmyeon": o["eupmyeon"],
                    "entry_node_id": o["entry_node_id"]},
        "origin_node": on, "origin_cell": road.node_cell[on], "origin_IB": [list(x) for x in row["origin_ib"]],
        "fire_arrival_at_village_s": row["A"],
        "shelters": shelters,
        "claims": {"windows": [list(x) for x in row["windows"]], "latest_departure_s": row["L"],
                   "leave_by_s": row["leave_by"], "road_cut_s": cut, "cut_kind": kind},
        "witnesses": wit,
        "stage": {"thresholds": {"immediate_hours": st["immediate_hours"], "standby_hours": st["standby_hours"]},
                  "now": row["stage_now"], "at_road_cut": row["stage_at_cut"], "flag": row["flag"]},
        "times_are": "seconds after the issue time; legs are [EDGE, edge index, start, end] or [WAIT, node, start, end]",
    }


def write_village(cdir: Path, row, ctx, inst_sha) -> Path:
    vdir = cdir / "villages"
    vdir.mkdir(parents=True, exist_ok=True)
    p = vdir / ("%s.json" % safe_id(row["origin"]["id"]))
    p.write_bytes(json.dumps(village_doc(row, ctx, inst_sha), ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8") + b"\n")
    return p


README = """# 인증서 / Certificates

모델 출력 · 참고용 · 명령 아님 / Model output · advisory · not an order

이 폴더만으로 (이 도구 없이) 모든 마을의 답을 다시 검증할 수 있습니다. Python 3.10+ 표준 라이브러리만 필요합니다.
Every village's answer can be re-verified from this folder alone, without the tool. Python 3.10+ standard library only.

    python3 verify_certificate.py .

* `instance.json.gz` — 도로망, 셀별 화재 도달(폐쇄) 초, 거기서 나온 폐쇄 구간(B, W). The road graph, the per-cell
  closure seconds and the masks derived from them.
* `villages/<id>.json` — 마을별 주장(출발 가능 시간대, 출발 마감, 도로 차단, 단계, 경고)과 증거 경로.
  Per-village claims and witness journeys.
* `checker.py` — research/kcf-theorem/checker.py 원본 그대로 (독립 경로 검사기). The independent route checker, verbatim.
* `verify_certificate.py` — 검사 항목은 파일 첫머리에 적혀 있습니다. What it checks is listed at its top.
"""
