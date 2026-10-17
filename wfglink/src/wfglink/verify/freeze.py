"""Freezing the evaluation protocol (python -m wfglink verify freeze).

`freeze(draft_yaml, out_dir, fill)` reads the protocol draft (YAML with FILLED_AT_FREEZE in the
values still to fill), fills those values line by line (comments kept), refuses when any
FILLED_AT_FREEZE remains, and writes out_dir/protocol.yaml and out_dir/protocol.sha256 (the
SHA-256 of the file's bytes, as `sha256sum` writes it: "<hex>  protocol.yaml").

Values filled (key paths of the draft; fill["values"] {dotted.path: value} overrides any):
- created: now in Asia/Shanghai;
- source_identity.scoring_commit: fill["scoring_commit"], else the current git commit
  (read only; a dirty tree is noted);
- source_identity.default_config_sha256: the hash a default run records as config_sha256
  (provenance.sha256_json of configs/default.yaml loaded);
- populations.<population>.recordings: the clip ids of the window sets fill["windows"]
  {population: [verify windows folder, ...]} names;
- annotation.windows.per_recording {clip: windows}, tile_px {clip: [w, h]} and enlargement
  (the scale, one number when all sets agree) from those folders' windows.json.
The window sets must have the draft's annotation.windows.seed and frames_per_window. A
population's recordings list filled from the window sets holds only recordings with windows;
a note says so (a tracking-only recording the draft lists without windows is given with
fill["values"], verify freeze --set). A recording may belong to one population only: a clip
id or video SHA-256 of window sets in two populations, a window set of a recording that
populations.development lists, or a clip id in the recordings of two populations of the
frozen protocol is refused.

Scoring inputs. freeze appends the keys verify eval reads: name (run_id), sealed (true) and
truth, one entry per window set: population, recording (clip id), sealed (true for the
populations in fill["sealed_populations"], default sealed_test), window_set_id,
windows.json and manifest SHA-256, video_sha256, segment_s, and the window set's truth.json
(fill["truth"]: truth.json files, matched to the sets by window_set_id) as a path relative to
the protocol and its SHA-256. A window set without truth is refused unless
fill["allow_missing_truth"]. evaluate.load_protocol reads this YAML (normalise_protocol maps
the draft's target names), and evaluate_run picks the entry of a run's video and segment.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

MARK = "FILLED_AT_FREEZE"
APPENDED = ("name", "sealed", "truth")


class FreezeError(ValueError):
    """The protocol cannot be frozen as given."""


_KEY = re.compile(r"^(\s*)([A-Za-z_][\w\-]*)\s*:(.*)$")


def key_paths(lines: list[str]) -> list[tuple[int, str]]:
    """(line index, dotted key path) of every mapping key line (block style)."""
    stack: list[tuple[int, str]] = []
    out = []
    for i, ln in enumerate(lines):
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = _KEY.match(ln)
        if not m:
            continue
        ind = len(m.group(1))
        while stack and stack[-1][0] >= ind:
            stack.pop()
        stack.append((ind, m.group(2)))
        out.append((i, ".".join(k for _, k in stack)))
    return out


def _split_comment(value: str) -> tuple[str, str]:
    """(value, comment with its leading spaces) of the text after a key's colon."""
    m = re.search(r"(\s+#.*)$", value)
    if m and value[:m.start()].count('"') % 2 == 0:
        return value[:m.start()], m.group(1)
    return value, ""


def _windows_records(windows: dict[str, list]) -> list[dict[str, Any]]:
    from wfglink.provenance import sha256_file

    recs = []
    for pop, dirs in (windows or {}).items():
        for d in dirs:
            p = Path(d) / "windows.json"
            if not p.is_file():
                raise FreezeError(f"{d}: no windows.json (not a folder written by verify windows)")
            wj = json.loads(p.read_text(encoding="utf-8"))
            recs.append({"population": pop, "dir": Path(d), "json": p, "json_sha256": sha256_file(p), "rec": wj})
    return recs


def _one_or_map(by_clip: dict[str, Any]) -> Any:
    vals = list(by_clip.values())
    if vals and all(v == vals[0] for v in vals):
        return vals[0]
    return by_clip


def _rel_to(path: Path, base: Path) -> str:
    try:
        return os.path.relpath(path.resolve(), base.resolve())
    except ValueError:
        return str(path.resolve())


def _recordings_of(pops: Any) -> dict[str, list[str]]:
    """Population -> its recordings list (populations given as mappings with a list)."""
    out: dict[str, list[str]] = {}
    for pop, v in (pops or {}).items() if isinstance(pops, dict) else ():
        r = v.get("recordings") if isinstance(v, dict) else None
        if isinstance(r, list):
            out[str(pop)] = [str(x) for x in r]
    return out


def _check_disjoint(recs: list[dict[str, Any]], parsed: dict[str, Any]) -> None:
    """A window set's recording (clip id, video SHA-256) in one population only, and never one
    the draft's development population lists."""
    seen: dict[tuple[str, str], str] = {}
    for r in recs:
        wj, pop = r["rec"], r["population"]
        for kind in ("clip_id", "video_sha256"):
            v = wj.get(kind)
            if not v:
                continue
            other = seen.setdefault((kind, str(v)), pop)
            if other != pop:
                raise FreezeError(f"{kind} {v} has window sets in two populations ({other}, {pop}): a recording "
                                  "belongs to one population only")
    dev = set(_recordings_of(parsed.get("populations")).get("development", []))
    for r in recs:
        if r["population"] != "development" and str(r["rec"].get("clip_id")) in dev:
            raise FreezeError(f"{r['rec'].get('clip_id')} is a development recording: its window set cannot be in "
                              f"{r['population']}")


def _check_populations(proto: dict[str, Any]) -> None:
    """No recording in the recordings of two populations of the frozen protocol."""
    where: dict[str, str] = {}
    for pop, recs in _recordings_of(proto.get("populations")).items():
        for c in recs:
            other = where.setdefault(c, pop)
            if other != pop:
                raise FreezeError(f"{c} is listed in two populations ({other}, {pop}): a recording belongs to one "
                                  "population only")


def freeze(draft_yaml: str | Path, out_dir: str | Path, fill: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fill, check and write the protocol (see the module notes). Returns a record of what was filled."""
    import yaml

    from wfglink.config import load_config
    from wfglink.provenance import git_state, now_shanghai, sha256_file, sha256_json
    from wfglink.verify.calibrate import flow

    fill = dict(fill or {})
    draft = Path(draft_yaml)
    text = draft.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text) or {}
    if not isinstance(parsed, dict):
        raise FreezeError(f"{draft} is not a YAML mapping")
    clash = [k for k in APPENDED if k in parsed]
    if clash:
        raise FreezeError(f"the draft already has the keys freeze writes: {clash}")
    out = Path(out_dir)
    notes: list[str] = []
    gs = git_state()
    values: dict[str, Any] = {"created": fill.get("created") or now_shanghai(),
                              "source_identity.scoring_commit": fill.get("scoring_commit") or gs.get("git_commit"),
                              "source_identity.default_config_sha256": fill.get("default_config_sha256")
                              or sha256_json(load_config())}
    if not fill.get("scoring_commit") and gs.get("git_dirty"):
        notes.append("the working tree had uncommitted changes when the scoring commit was read")
    recs = _windows_records(fill.get("windows") or {})
    ann = ((parsed.get("annotation") or {}).get("windows") or {})
    for r in recs:
        wj = r["rec"]
        if ann.get("seed") not in (None, MARK) and int(wj.get("seed", -1)) != int(ann["seed"]):
            raise FreezeError(f"{r['dir']}: windows drawn with seed {wj.get('seed')}, the protocol says {ann['seed']}")
        if ann.get("frames_per_window") not in (None, MARK) and int(wj.get("k", -1)) != int(ann["frames_per_window"]):
            raise FreezeError(f"{r['dir']}: {wj.get('k')} frames per window, the protocol says "
                              f"{ann['frames_per_window']}")
    _check_disjoint(recs, parsed)
    if recs:
        pops = sorted({r["population"] for r in recs})
        given = fill.get("values") or {}
        for pop in pops:
            if pop not in (parsed.get("populations") or {}):
                raise FreezeError(f"population {pop!r} is not in the draft")
            key = f"populations.{pop}.recordings"
            values[key] = [r["rec"]["clip_id"] for r in recs if r["population"] == pop]
            if key not in given:
                notes.append(f"{key} was filled from the window sets only ({', '.join(values[key])}); a recording of "
                             "this population without windows (for example a tracking-only one) is not listed unless "
                             f"given with --set {key}=[...]: check it against the draft's comment")
        values["annotation.windows.per_recording"] = {r["rec"]["clip_id"]: int(r["rec"]["n_windows"]) for r in recs}
        values["annotation.windows.tile_px"] = _one_or_map({r["rec"]["clip_id"]: [int(v) for v in r["rec"]["tile_px"]]
                                                           for r in recs})
        values["annotation.windows.enlargement"] = _one_or_map({r["rec"]["clip_id"]: int(r["rec"]["scale"])
                                                               for r in recs})
    values.update(fill.get("values") or {})

    lines = text.splitlines()
    filled: dict[str, Any] = {}
    for i, path in key_paths(lines):
        m = _KEY.match(lines[i])
        val, comment = _split_comment(m.group(3))
        if val.strip() != MARK:
            continue
        if path not in values or values[path] is None:
            continue
        lines[i] = f"{m.group(1)}{m.group(2)}: {flow(values[path])}{comment}"
        filled[path] = values[path]
    left = [p for i, p in key_paths(lines) if _split_comment(_KEY.match(lines[i]).group(3))[0].strip() == MARK]
    stray = [i + 1 for i, ln in enumerate(lines) if MARK in _split_comment(ln)[0] and not ln.lstrip().startswith("#")]
    if left or stray:
        raise FreezeError(f"FILLED_AT_FREEZE remains at {left or stray}: give these values (fill['values'])")

    # Scoring inputs for verify eval.
    truth_files = fill.get("truth") or []
    if isinstance(truth_files, dict):
        truth_files = [p for v in truth_files.values() for p in v]
    by_set: dict[str, Path] = {}
    for tp in truth_files:
        tj = json.loads(Path(tp).read_text(encoding="utf-8"))
        sid = tj.get("window_set_id")
        if sid in by_set:
            raise FreezeError(f"two truth files for window set {sid}")
        by_set[str(sid)] = Path(tp)
    sealed_pops = set(fill.get("sealed_populations") or ("sealed_test",))
    entries = []
    for r in recs:
        wj = r["rec"]
        sid = str(wj.get("window_set_id"))
        tp = by_set.pop(sid, None)
        if tp is None and not fill.get("allow_missing_truth"):
            raise FreezeError(f"no truth.json for window set {sid} ({wj.get('clip_id')}, {r['dir']})")
        if tp is not None:
            tj = json.loads(tp.read_text(encoding="utf-8"))
            if tj.get("video_sha256") != wj.get("video_sha256"):
                raise FreezeError(f"{tp}: its video is not the window set's")
        entries.append({"population": r["population"], "recording": wj.get("clip_id"),
                        "sealed": r["population"] in sealed_pops, "window_set_id": sid,
                        "windows_json": _rel_to(r["json"], out), "windows_json_sha256": r["json_sha256"],
                        "manifest_sha256": wj.get("manifest_sha256"), "video_sha256": wj.get("video_sha256"),
                        "segment_s": wj.get("segment_s"), "roi_px": wj.get("roi_px"),
                        "path": _rel_to(tp, out) if tp is not None else None,
                        "sha256": sha256_file(tp) if tp is not None else None})
    if by_set:
        raise FreezeError(f"truth files for window sets that are not frozen: {sorted(by_set)}")
    tail = ["", "# Scoring inputs (written by verify freeze; verify eval reads name, sealed, truth and targets).",
            "# A run is scored against the truth entry of its video and segment start; a sealed entry once.",
            f"name: {flow(str(parsed.get('run_id') or fill.get('name') or 'protocol'))}", "sealed: true",
            "truth:" + ("" if entries else " []")]
    tail += [f"  - {flow(e)}" for e in entries]
    new = "\n".join(lines).rstrip("\n") + "\n" + "\n".join(tail) + "\n"
    back = yaml.safe_load(new)
    if not isinstance(back, dict) or back.get("truth") is None and entries:
        raise FreezeError("the frozen protocol does not read back as YAML")

    def walk(v):
        if isinstance(v, dict):
            return any(walk(x) for x in v.values())
        if isinstance(v, list):
            return any(walk(x) for x in v)
        return v == MARK

    if walk(back):
        raise FreezeError("FILLED_AT_FREEZE remains in the frozen protocol")
    _check_populations(back)
    out.mkdir(parents=True, exist_ok=True)
    pp = out / "protocol.yaml"
    pp.write_text(new, encoding="utf-8")
    sha = sha256_file(pp)
    (out / "protocol.sha256").write_text(f"{sha}  protocol.yaml\n", encoding="utf-8")
    return {"protocol": str(pp), "sha256": sha, "filled": filled, "truth": entries, "notes": notes,
            "draft": str(draft), "draft_sha256": sha256_file(draft)}


def read_sha256(path_or_hex: str) -> str:
    """A pinned SHA-256 given as hex or as a protocol.sha256 file."""
    p = Path(path_or_hex)
    if len(path_or_hex) != 64 and p.is_file():
        return p.read_text(encoding="utf-8").split()[0].strip().lower()
    return path_or_hex.strip().lower()
