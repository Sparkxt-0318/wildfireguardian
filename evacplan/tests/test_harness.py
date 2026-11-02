"""The harness: CSV schema, upserts, the leaderboard, the test-set guard, oracle-only scoring and
the bench lock; the 2026-11-01 comparison rules (5 repeats with median and range, one table per host,
the bar for beating B2, safety-margin columns and the margin figure). Runs on a throw-away split of
SYNTHETIC instances (seeds 9301-9303, outside the frozen split) and on hand-made rows in temporary
folders."""
import csv
import importlib.metadata
import json
import os
import platform
import socket
import struct
import subprocess
import sys
import textwrap
import zlib

import numpy as np
import pytest

import hazard_contract as hc
from evacplan import Board, ClassCounts, Itinerary, Oracle, Solution, State, load_instance, load_scenario_set
from evacplan.cli import main
from evacplan.generators import SyntheticConfig
from evacplan.harness import (
    COLUMNS, FACILITY_COLUMNS, TestSetRefused, bench_guard, git_commit, load_benchlock, lock_held_by_ancestor,
    make_row, read_rows, row_config, run, speed_rows, upsert_rows,
)
from evacplan.instances import Split, SplitEntry, build_split, write_split
from evacplan.methods import Method, MethodResult, available, get_method, register


@pytest.fixture(scope="module")
def mini(tmp_path_factory):
    root = tmp_path_factory.mktemp("harness")
    split = build_split({
        "dev": [SyntheticConfig(size="S", tightness=0.5, graph="grid", seed=9301),
                SyntheticConfig(size="S", tightness=0.8, graph="geo", seed=9302)],
        "test": [SyntheticConfig(size="S", tightness=0.5, graph="grid", seed=9303)],
    }, frozen="test-fixture")
    write_split(split, root / "SPLIT.json")
    return root, split


def paths(root, tag):
    return dict(split_path=root / "SPLIT.json", cache_dir=root / "cache", results_dir=root / f"results-{tag}",
                leaderboard_path=root / f"LEADERBOARD-{tag}.md")


def rows_of(path):
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        return reader.fieldnames, list(reader)


def test_noop_rows_have_the_exact_schema(mini):
    from evacplan.harness import MARGINS_MIN, host_string
    root, split = mini
    p = paths(root, "schema")
    out = run("noop", "dev", 60, seeds=[0, 1], lock="no", log=lambda s: None, **p)
    assert len(out) == 4
    header, rows = rows_of(p["results_dir"] / "noop.csv")
    assert tuple(header) == COLUMNS == ("instance", "method", "seed", "delivered_checked", "unresolved",
                                        "model_no_route", "makespan_s", "min_slack_s", "delivered_slack_ge_0m",
                                        "delivered_slack_ge_5m", "delivered_slack_ge_15m", "delivered_slack_ge_30m",
                                        "runtime_s", "best_bound", "gap", "commit", "config", "host")
    fps = {e.id: e.fingerprint for e in split.entries("dev")}
    assert sorted((r["instance"], r["seed"]) for r in rows) == sorted((i, s) for i in fps for s in ("0", "1"))
    for r in rows:
        assert r["method"] == "noop" and r["delivered_checked"] == r["unresolved"] == r["model_no_route"] == "0"
        assert r["makespan_s"] == r["min_slack_s"] == r["best_bound"] == r["gap"] == ""
        assert r["delivered_slack_ge_0m"] == r["delivered_slack_ge_5m"] == r["delivered_slack_ge_15m"] \
            == r["delivered_slack_ge_30m"] == "0"
        assert 0 <= float(r["runtime_s"]) < 60 and r["commit"]
        assert r["host"] == host_string()                      # the machine, its CPU model and Python
        cfg = json.loads(r["config"])
        assert cfg["set"] == "dev" and cfg["budget_s"] == 60.0 and cfg["method"] == {} and cfg["label"] == "SYNTHETIC"
        assert cfg["instance"]["fingerprint"] == fps[r["instance"]] and cfg["instance"]["config"]["seed"] in (9301, 9302)
        assert cfg["oracle"] and cfg["hazard_contract"]
        assert cfg["delivered_by_margin_min"] == {str(m): 0 for m in MARGINS_MIN}
    plans = sorted((p["results_dir"] / "runs" / "noop" / "dev-b60").glob("*.result.json"))
    assert len(plans) == 4 and json.loads(plans[0].read_text())["label"] == "SYNTHETIC"


def _installed(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def test_rows_record_contract_and_package_versions(mini):
    """Provenance: every row's config holds the contract format (``CONTRACT_VERSION``) and the package
    versions that can change results: hazard_contract's own ``__version__`` (1.0.1 changed contact at exact
    boundaries while the format stayed 1.0), numpy, ortools and highspy."""
    root, split = mini
    p = paths(root, "versions")
    r = run("noop", "dev", 60, seeds=[0], lock="no", log=lambda s: None, **p)[0]
    cfg = json.loads(r["config"])
    assert cfg["hazard_contract"] == hc.CONTRACT_VERSION
    v = cfg["versions"]
    assert v["hazard_contract"] == hc.__version__ and v["numpy"] == np.__version__
    assert v["ortools"] == _installed("ortools") and v["highspy"] == _installed("highspy")


def test_dirty_check_covers_evacplan_hazard_contract_and_program(tmp_path):
    """``commit`` gets ``+dirty`` for uncommitted changes in evacplan/, hazard_contract/ or program/ (the
    generated evacplan/LEADERBOARD.md, its margin figures under evacplan/figures/ and the result rows under
    evacplan/results/ excepted), not for the rest of the repository."""
    repo = tmp_path / "repo"
    for d in ("evacplan", "hazard_contract", "program", "other"):
        (repo / d).mkdir(parents=True)
        (repo / d / "f.txt").write_text("x\n")
    (repo / "evacplan" / "LEADERBOARD.md").write_text("lb\n")
    (repo / "evacplan" / "results").mkdir()
    (repo / "evacplan" / "results" / "b1_greedy.csv").write_text("row\n")    # committed result rows

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c",
                        "commit.gpgsign=false", *args], cwd=repo, check=True, capture_output=True)
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    ep = repo / "evacplan"
    sha = git_commit(ep)
    assert len(sha) == 40 and "+" not in sha
    (ep / "LEADERBOARD.md").write_text("regenerated\n")
    (ep / "results" / "b1_greedy.csv").write_text("row\nnew row\n")     # a run upserts its rows
    (ep / "results" / "noop.csv").write_text("row\n")                    # or writes a new file
    (ep / "results" / "runs").mkdir()
    (ep / "results" / "runs" / "plan.json").write_text("{}\n")
    (ep / "figures").mkdir()                                            # the leaderboard's margin figures
    (ep / "figures" / "margin_dev_60s_host-0000.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (repo / "other" / "f.txt").write_text("changed\n")
    assert git_commit(ep) == sha
    for d in ("hazard_contract", "program", "evacplan"):
        (repo / d / "f.txt").write_text("changed\n")
        assert git_commit(ep) == sha + "+dirty", d
        git("checkout", "--", f"{d}/f.txt")
    (repo / "program" / "new.py").write_text("x = 1\n")         # untracked files count too
    assert git_commit(ep) == sha + "+dirty"


def test_upsert_and_equal_budget_leaderboard(mini):
    root, split = mini
    p = paths(root, "upsert")
    run("noop", "dev", 60, seeds=[0, 1], lock="no", log=lambda s: None, **p)
    run("noop", "dev", 60, seeds=[1], lock="no", log=lambda s: None, **p)                 # replaces, no duplicates
    run("noop", "dev", 30, seeds=[0], instances=[split.ids("dev")[0]], lock="no", log=lambda s: None, **p)
    rows = read_rows(p["results_dir"] / "noop.csv")
    assert len(rows) == 5
    assert sorted(json.loads(r["config"])["budget_s"] for r in rows) == [30.0] + [60.0] * 4
    text = p["leaderboard_path"].read_text()
    assert "## dev, budget 30 s, host " in text and "## dev, budget 60 s, host " in text
    assert "| noop | SYNTHETIC | 2 | 2 | 0 (0.0%) | 0 |" in text            # the seeds agree: one value, no range
    assert "| noop | SYNTHETIC | 1 | 1 | 0 (0.0%) | 0 |" in text
    assert all(i in text for i in split.ids("dev")) and not any(i in text for i in split.ids("test"))
    assert "**SYNTHETIC** rows are SYNTHETIC instances" in text and "equal wall-clock budgets" in text
    # what comes from the oracle, what from the methods' own proofs, what from the harness clock
    assert "Every number comes from" not in text
    assert "come from `evacplan.oracle`" in text and "come from the methods' own proofs" in text
    assert "harness's wall clock" in text
    with pytest.raises(KeyError):
        run("noop", "dev", 60, instances=["SYNTHETIC-nope"], lock="no", log=lambda s: None, **p)


def test_test_set_is_refused_without_approval(mini):
    root, split = mini
    p = paths(root, "refuse")
    with pytest.raises(TestSetRefused):
        run("noop", "test", 60, lock="no", log=lambda s: None, **p)
    assert not p["results_dir"].exists() and not p["leaderboard_path"].exists()
    assert not any((root / "cache" / i).exists() for i in split.ids("test"))
    args = ["run", "--method", "noop", "--set", "test", "--budget-s", "60", "--lock", "no",
            "--split", str(p["split_path"]), "--cache-dir", str(p["cache_dir"]),
            "--results-dir", str(p["results_dir"]), "--leaderboard", str(p["leaderboard_path"])]
    assert main(args) == 3
    assert main(["instances", "--set", "test", "--materialize", "--split", str(p["split_path"]),
                 "--cache-dir", str(p["cache_dir"])]) == 3
    assert not p["results_dir"].exists()


def test_cli_run_and_leaderboard(mini, capsys):
    root, split = mini
    p = paths(root, "cli")
    common = ["--split", str(p["split_path"]), "--cache-dir", str(p["cache_dir"]), "--results-dir",
              str(p["results_dir"]), "--leaderboard", str(p["leaderboard_path"])]
    assert main(["run", "--method", "noop", "--set", "dev", "--budget-s", "60", "--seeds", "0,2", "--lock", "no",
                 *common]) == 0
    assert {r["seed"] for r in read_rows(p["results_dir"] / "noop.csv")} == {"0", "2"}
    p["leaderboard_path"].unlink()
    assert main(["leaderboard", *common]) == 0 and p["leaderboard_path"].is_file()
    assert main(["instances", "--set", "dev", "--split", str(p["split_path"])]) == 0
    assert "SYNTHETIC-S-grid-t50-s9301" in capsys.readouterr().out


class _Claims(Method):
    """Returns a plan that boards a resident away from the facility and claims a bound."""

    name = "claims"

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline):
        v, f = instance.vehicles[0], instance.facilities[0]
        plan = Solution(instance=instance.name, method=self.name,
                        itineraries=[Itinerary(vehicle=v.id, actions=[
                            Board(facility=f.id, counts=ClassCounts(ambulatory=1))])])
        return MethodResult(plan, best_bound=10.0, info={"delivered": 999})


def test_final_states_come_from_the_oracle(mini):
    root, split = mini
    p = paths(root, "oracle")
    register("claims-test", _Claims, replace=True)
    assert "claims-test" in available()
    rows = run("claims-test", "dev", 60, instances=[split.ids("dev")[0]], lock="no", log=lambda s: None, **p)
    inst = load_instance(p["cache_dir"] / split.ids("dev")[0] / "instance.json")
    plan = Oracle(inst, load_scenario_set(inst)).check_plan(_Claims().solve(inst, None, budget_s=1, seed=0,
                                                                            deadline=0).solution)
    (r,) = rows
    assert plan.delivered_total == 0 and plan.model_no_route_total == 1
    assert r["delivered_checked"] == "0" and r["model_no_route"] == str(plan.model_no_route_total)
    assert r["unresolved"] == str(plan.unresolved_total) and r["best_bound"] == "10.000" and r["gap"] == "1.000000"


def test_gap_definition():
    class P:
        delivered_total, unresolved_total, model_no_route_total, makespan_s, min_slack_s = 4, 1, 0, 100.0, 5.0

    class E:
        id, generator, generator_version, config, fingerprint, label = "x", "g", "v", {}, "f", "SYNTHETIC"
    kw = dict(entry=E, set_name="dev", method_name="m", method_config={}, seed=0, budget_s=60, plan=P,
              runtime_s=1.0, commit="c", host="h", margins=dict.fromkeys(MARGINS, 4))   # P is not an oracle result
    assert make_row(best_bound=10, **kw)["gap"] == "0.600000"
    assert make_row(best_bound=0, **kw)["gap"] == "0.000000"
    assert make_row(best_bound=None, **kw)["gap"] == ""
    assert get_method("noop").name == "noop"
    with pytest.raises(KeyError):
        get_method("b9")


def test_bench_lock_is_taken_and_never_deadlocks_under_a_parent(tmp_path, monkeypatch):
    lock = tmp_path / "bench.lock"
    monkeypatch.setenv("WFG_BENCH_LOCK", str(lock))
    bl = load_benchlock()
    with bench_guard("yes", "evacplan-test", log=lambda s: None) as state:
        assert state.startswith("acquired") and "evacplan-test" in lock.read_text()
    assert lock.read_text() == ""
    lock.write_text(f"other pid=999999 host={socket.gethostname()} since=now\n")
    assert not lock_held_by_ancestor(bl)
    with bl.bench_lock("parent-holds-it"):
        assert f"pid={os.getpid()}" in lock.read_text()
        child = textwrap.dedent("""
            from evacplan.harness import bench_guard
            with bench_guard("auto", "child", log=lambda s: None) as state:
                print(state)
        """)
        out = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, timeout=60,
                             env={**os.environ, "WFG_BENCH_LOCK": str(lock)})
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == "held by a parent process"


def test_per_facility_rows_deadlines_and_outcomes(mini):
    root, split = mini
    p = paths(root, "facilities")
    out = run("b1_greedy", "dev", 60, seeds=[0], lock="no", log=lambda s: None, **p)
    fac_csv = p["results_dir"] / "b1_greedy.facilities.csv"
    header, frows = rows_of(fac_csv)
    assert tuple(header) == FACILITY_COLUMNS == (
        "instance", "method", "seed", "facility", "mobility_class", "residents", "release_s", "deadline_state",
        "deadline_cause", "arrive_by_s", "leave_by_s", "deadline_shelter", "unservable", "delivered_checked",
        "unresolved", "model_no_route", "not_planned", "first_board_s", "last_leave_s", "commit", "config", "host")
    assert read_rows(fac_csv) == frows
    main_rows = {r["instance"]: r for r in out}
    for inst_id in split.ids("dev"):
        inst = load_instance(p["cache_dir"] / inst_id / "instance.json")
        mine = [r for r in frows if r["instance"] == inst_id]
        assert len(mine) == sum(1 for f in inst.facilities for c in range(3) if f.residents.vector()[c])
        assert sum(int(r["delivered_checked"]) for r in mine) == int(main_rows[inst_id]["delivered_checked"])
        assert sum(int(r["residents"]) for r in mine) == inst.residents_total
        for r in mine:
            n = int(r["residents"])
            assert int(r["delivered_checked"]) + int(r["unresolved"]) + int(r["model_no_route"]) \
                + int(r["not_planned"]) == n
            assert r["deadline_state"] in ("checked", "model_no_route", "unresolved")
            assert int(r["unservable"]) == (n if r["deadline_state"] == "model_no_route" else 0)
            if r["deadline_state"] == "checked":
                assert float(r["arrive_by_s"]) <= float(r["leave_by_s"]) and r["deadline_shelter"]
                if r["last_leave_s"]:                             # the plan leaves by the deadline
                    assert float(r["last_leave_s"]) <= float(r["leave_by_s"])
            if r["first_board_s"]:
                assert float(r["first_board_s"]) >= float(r["release_s"])
            assert r["commit"] == main_rows[inst_id]["commit"] and r["config"] == main_rows[inst_id]["config"]
        deadlines = json.loads((p["results_dir"] / "runs" / "b1_greedy" / "dev-b60" / f"{inst_id}.deadlines.json")
                               .read_text())
        assert len(deadlines) == len(mine) and all("scope" in d for d in deadlines)
    text = p["leaderboard_path"].read_text()
    assert "| unservable |" in text and "**unservable**" in text and "b1_greedy" in text
    run("b1_greedy", "dev", 60, seeds=[0], lock="no", log=lambda s: None, **p)     # upsert: no duplicates
    assert len(read_rows(fac_csv)) == len(frows)


def test_aliases_s_only_methods_bounds_and_sizes(tmp_path_factory):
    """``--method B2`` writes b2_vrptw rows; B3 runs on S instances only (no row for M) and its proven bound
    appears as the instance's best bound; the leaderboard adds a size table."""
    root = tmp_path_factory.mktemp("harness-b23")
    split = build_split({"dev": [SyntheticConfig(size="S", tightness=0.75, graph="geo", seed=9311),
                                 SyntheticConfig(size="M", tightness=0.5, graph="grid", seed=9312)]},
                        frozen="test-fixture")
    write_split(split, root / "SPLIT.json")
    p = paths(root, "b23")
    s_id, m_id = split.ids("dev")
    b2 = run("B2", "dev", 6, lock="no", log=lambda s: None, **p)                   # equal budgets: one table
    assert {r["method"] for r in b2} == {"b2_vrptw"} and (p["results_dir"] / "b2_vrptw.csv").is_file()
    assert not (p["results_dir"] / "B2.csv").exists()
    for row in b2:                                     # how deep B2's search got, in the row (never scored)
        diag = json.loads(row["config"])["diagnostics"]
        assert diag["solutions"] >= 1 and isinstance(diag["objective"], int) and diag["search_s"] > 0
    logs: list[str] = []
    b3 = run("b3", "dev", 6, lock="no", log=logs.append, **p)
    assert [r["instance"] for r in b3] == [s_id] and any("skipped" in x and m_id in x for x in logs)
    (r,) = b3
    assert r["method"] == "b3_mip" and r["best_bound"] and r["gap"]
    assert int(r["delivered_checked"]) <= float(r["best_bound"]) <= 40
    b2_s = next(x for x in b2 if x["instance"] == s_id)
    assert int(b2_s["delivered_checked"]) <= float(r["best_bound"])          # the bound covers every method
    assert float(r["gap"]) == pytest.approx((float(r["best_bound"]) - int(r["delivered_checked"])) / float(r["best_bound"]))
    text = p["leaderboard_path"].read_text()
    assert "| best bound |" in text and "by instance size" in text
    line = next(x for x in text.splitlines() if x.startswith(f"| {s_id} |"))
    assert f"| {float(r['best_bound']):g} |" in line
    assert "| b3_mip | " in text and "| b3_mip | SYNTHETIC | 1 | 1 |" in text


# ------------------------------------------------------------------ the 2026-11-01 comparison rules
MARGINS = (0, 1, 2, 5, 10, 15, 20, 30, 45, 60)       # minutes: the curve in each row's config
OLD_COLUMNS = ("instance", "method", "seed", "delivered_checked", "unresolved", "model_no_route", "makespan_s",
               "min_slack_s", "runtime_s", "best_bound", "gap", "commit", "config", "host")      # before 2026-11-01


def _split(ids, residents=100, size="M"):
    return Split(frozen="test-fixture", sets={"dev": [
        SplitEntry(id=i, generator="g", generator_version="v", config={"size": size}, fingerprint="f",
                   synthetic=True, stats={"residents": residents}) for i in ids]})


def _rows(method, outcomes, budget=60.0, host="h", margins=None):
    """Result rows, as the harness writes them, for ``{(instance, seed): (delivered, unresolved)}`` on ``host``
    (residents per instance: 100). ``margins``: ``{(instance, seed): {minutes: delivered}}``; default: every
    delivered resident has at least 60 min of slack."""
    out = []
    for (inst, seed), (dl, un) in outcomes.items():
        curve = (margins or {}).get((inst, seed)) or {m: dl for m in MARGINS}
        cfg = {"set": "dev", "budget_s": float(budget), "method": {}, "label": "SYNTHETIC", "oracle": "o",
               "instance": {"generator": "g", "generator_version": "v", "config": {}, "fingerprint": "f"},
               "hazard_contract": "1.0", "versions": {}, "delivered_by_margin_min": {str(m): curve[m] for m in MARGINS}}
        out.append({"instance": inst, "method": method, "seed": str(seed), "delivered_checked": str(dl),
                    "unresolved": str(un), "model_no_route": "0", "makespan_s": "10.0", "min_slack_s": "5.0",
                    **{f"delivered_slack_ge_{m}m": str(curve[m]) for m in (0, 5, 15, 30)},
                    "runtime_s": "1.0000", "best_bound": "", "gap": "", "commit": "c" * 40,
                    "config": json.dumps(cfg, sort_keys=True, separators=(",", ":")), "host": host})
    return out


def _curve(delivered, **at):
    """A margin curve: ``delivered`` up to the first margin named in ``at`` (``m15=80`` means 80 residents at
    >= 15 min), then the values given, carried forward."""
    out, cur = {}, delivered
    for m in MARGINS:
        cur = at.get(f"m{m}", cur)
        out[m] = cur
    return out


def _table(text, heading):
    """The lines of the first Markdown table after the first line that starts with ``heading``."""
    lines = text.splitlines()
    i = next(k for k, x in enumerate(lines) if x.startswith(heading))
    i = next(k for k in range(i, len(lines)) if lines[k].startswith("|"))
    j = next((k for k in range(i, len(lines)) if not lines[k].startswith("|")), len(lines))
    return lines[i:j]


def _sections(text):
    """``## `` heading -> the text under it."""
    out, head = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            head = line
            out[head] = []
        elif head is not None:
            out[head].append(line)
    return {h: "\n".join(v) for h, v in out.items()}


def test_leaderboard_shows_median_and_range_over_repeats():
    """5-repeat rule (DECISIONS 2026-11-01): per-instance cells show the median over seeds, then [min-max] when
    the seeds differ; method totals show the median of the per-seed totals, then their [min-max]; seeds that
    agree show one value. The same holds for the safety-margin columns. (The old leaderboard showed means:
    180 [160-190] delivered and 20 [10-40] unresolved for b2_vrptw here.)"""
    from evacplan.harness import render_leaderboard
    split = _split(("I1", "I2"))
    margins = {("I2", 0): _curve(90, m10=85, m15=80, m20=70, m30=50, m45=20, m60=0),
               ("I2", 1): _curve(60, m10=40, m15=30, m20=20, m30=10, m45=0),
               ("I2", 2): _curve(90, m5=88, m10=86, m15=85, m20=80, m30=60, m45=30, m60=5)}
    rows = _rows("b2_vrptw", {("I1", 0): (100, 0), ("I1", 1): (100, 0), ("I1", 2): (100, 0),
                              ("I2", 0): (90, 10), ("I2", 1): (60, 40), ("I2", 2): (90, 10)}, margins=margins)
    rows += _rows("b1_greedy", {("I1", 0): (70, 0), ("I2", 0): (50, 0)})
    text = render_leaderboard(rows, split)
    # per-seed totals: delivered 190, 160, 190 and unresolved 10, 40, 10 -> medians 190 and 10
    b2 = next(x for x in text.splitlines() if x.startswith("| b2_vrptw |"))
    assert b2.startswith("| b2_vrptw | SYNTHETIC | 2 | 3 | 190 (95.0%) [160–190] | 10 [10–40] |")
    # slack >= 5, 15, 30 min per seed: 190, 160, 188 / 180, 130, 185 / 150, 110, 160
    assert "| 188 [160–190] | 180 [130–185] | 150 [110–160] |" in b2
    b1 = next(x for x in text.splitlines() if x.startswith("| b1_greedy |"))
    assert b1.startswith("| b1_greedy | SYNTHETIC | 2 | 1 | 120 (60.0%) | 0 |") and "| 120 | 120 | 120 |" in b1
    delivered = _table(text, "Delivered (checked) per instance")
    assert next(x for x in delivered if x.startswith("| I2 |")).endswith("| 50 | 90 [60–90] |")   # b1, then b2
    assert next(x for x in delivered if x.startswith("| I1 |")).endswith("| 70 | 100 |")          # seeds agree
    unresolved = _table(text, "Unresolved per instance")
    assert next(x for x in unresolved if x.startswith("| I2 |")).endswith("| 0 | 10 [10–40] |")
    slack15 = _table(text, "Delivered with slack ≥ 15 min per instance")
    assert next(x for x in slack15 if x.startswith("| I2 |")).endswith("| 50 | 80 [30–85] |")
    assert "median" in text and "worst of 5 repeats" in text and "seeds 0-4" in text
    assert "mean over seeds" not in text and "minimum dev total exceeds B2's maximum" not in text


def test_host_string_names_the_cpu_model(tmp_path):
    """Rows record the host with its CPU model: Linux /proc/cpuinfo "model name", macOS sysctl
    machdep.cpu.brand_string, else platform.processor() or "unknown cpu"."""
    from evacplan.harness import cpu_model, host_string
    info = tmp_path / "cpuinfo"
    info.write_text("processor\t: 0\nvendor_id\t: GenuineIntel\nmodel name\t: Intel(R) Xeon(R) Processor @ 2.80GHz\n\n"
                    "processor\t: 1\nmodel name\t: Intel(R) Xeon(R) Processor @ 2.80GHz\n")
    assert cpu_model("Linux", cpuinfo=info) == "Intel(R) Xeon(R) Processor @ 2.80GHz"
    calls = []

    def sysctl(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="Apple M2 Pro\n", stderr="")
    assert cpu_model("Darwin", runner=sysctl) == "Apple M2 Pro"
    assert calls == [["sysctl", "-n", "machdep.cpu.brand_string"]]

    def broken(cmd, **kw):
        raise OSError("no sysctl")
    assert cpu_model("Darwin", runner=broken, processor="arm") == "arm"
    assert cpu_model("Linux", cpuinfo=tmp_path / "missing", processor="") == "unknown cpu"
    h = host_string()
    assert cpu_model() in h and socket.gethostname() in h and f"python {platform.python_version()}" in h
    assert f"{os.cpu_count()} cpu" in h


def test_host_string_names_the_boot_session_on_a_virtual_machine(tmp_path):
    """On a virtual machine the CPU label does not name the hardware behind it: two cloud containers with the
    same host string ran B0/B1 1.7-2.4x apart (program/DECISIONS.md, 2026-11-01). There the host string ends with
    the boot session, so every container session is its own host; bare metal keeps the plain string."""
    from evacplan.harness import host_class, host_string, machine_session
    vm, metal, boot = tmp_path / "cpuinfo_vm", tmp_path / "cpuinfo_metal", tmp_path / "boot_id"
    vm.write_text("processor\t: 0\nmodel name\t: Intel(R) Xeon(R) Processor @ 2.80GHz\n"
                  "flags\t\t: fpu vme sse2 hypervisor avx2\n")
    metal.write_text("processor\t: 0\nmodel name\t: AMD Ryzen 9 7950X\nflags\t\t: fpu vme sse2 avx2\n")
    boot.write_text("ff671362-8279-4136-bcca-5e5e060f4115\n")
    assert machine_session("Linux", cpuinfo=vm, boot_id=boot) == "ff671362"
    assert machine_session("Linux", cpuinfo=metal, boot_id=boot) == ""
    assert machine_session("Linux", cpuinfo=vm, boot_id=tmp_path / "missing") == "unknown"

    def sysctl(answers):
        def run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, stdout=answers[cmd[-1]] + "\n", stderr="")
        return run
    mac_vm = sysctl({"kern.hv_vmm_present": "1", "kern.bootsessionuuid": "1A2B3C4D-0000-4000-8000-000000000000"})
    assert machine_session("Darwin", runner=mac_vm) == "1a2b3c4d"
    assert machine_session("Darwin", runner=sysctl({"kern.hv_vmm_present": "0"})) == ""
    assert machine_session("Windows") == ""
    plain = "vm (Linux x86_64, Intel(R) Xeon(R) Processor @ 2.80GHz, 4 cpu, python 3.12.3)"
    assert host_string(session="ff671362").endswith(", vm boot ff671362)")
    assert host_string(session="") == host_class(host_string(session="ff671362"))
    assert host_class(plain[:-1] + ", vm boot ff671362)") == plain and host_class(plain) == plain
    s = machine_session()
    assert host_string().endswith(f", vm boot {s})" if s else f"python {platform.python_version()})")


def test_upsert_is_keyed_by_host_and_hosts_are_never_pooled(tmp_path):
    """The upsert key is (set, budget, instance, method, seed, host); the leaderboard renders one table per (set,
    budget, host), names the host above it and never pools or compares rows of different hosts."""
    from evacplan.harness import render_leaderboard
    split = _split(("I1", "I2"))
    path = tmp_path / "b1_greedy.csv"
    upsert_rows(path, _rows("b1_greedy", {("I1", 0): (70, 0), ("I2", 0): (50, 0)}, host="host-A"))
    upsert_rows(path, _rows("b1_greedy", {("I1", 0): (10, 0), ("I2", 0): (20, 0)}, host="host-B"))
    assert len(read_rows(path)) == 4                  # the same keys on another host: kept, not replaced
    upsert_rows(path, _rows("b1_greedy", {("I1", 0): (71, 0)}, host="host-A"))           # same host: replaced
    rows = read_rows(path)
    assert sorted((r["host"], r["instance"], r["delivered_checked"]) for r in rows) == [
        ("host-A", "I1", "71"), ("host-A", "I2", "50"), ("host-B", "I1", "10"), ("host-B", "I2", "20")]
    text = render_leaderboard(rows, split, observations=[])
    sections = _sections(text)
    (a,) = [b for h, b in sections.items() if h == "## dev, budget 60 s, host host-A"]
    (b,) = [b for h, b in sections.items() if h == "## dev, budget 60 s, host host-B"]
    assert "| b1_greedy | SYNTHETIC | 2 | 1 | 121 (60.5%) | 0 |" in a
    assert "| b1_greedy | SYNTHETIC | 2 | 1 | 30 (15.0%) | 0 |" in b
    assert next(x for x in _table(a, "Delivered (checked) per instance") if x.startswith("| I1 |")).endswith("| 71 |")
    assert next(x for x in _table(b, "Delivered (checked) per instance") if x.startswith("| I1 |")).endswith("| 10 |")
    assert "best-of-baselines total 121" in a and "best-of-baselines total 30" in b
    assert "[10–71]" not in text and "40.5" not in text and "151" not in text      # nothing pooled
    assert "never pooled or compared" in text


def _five(method, totals, host="host-A", missing=()):
    """Rows of ``method`` on I1 and I2, one seed per entry of ``totals``: I1 gets 60, I2 the rest of the total;
    ``missing``: (instance, seed) pairs with no row."""
    out = {(i, s): (v, 0) for s, t in enumerate(totals) for i, v in (("I1", 60), ("I2", t - 60))}
    return _rows(method, {k: v for k, v in out.items() if k not in missing}, host=host)


def _bar_fixture():
    rows = _rows("b1_greedy", {(i, s): (v, 0) for s in range(5) for i, v in (("I1", 70), ("I2", 50))}, host="host-A")
    rows += _rows("b0_independent", {("I1", 0): (40, 0), ("I2", 0): (30, 0)}, host="host-A")
    # B2: per-seed totals 119, 119, 116, 117, 118 (the per-instance maxima, 64 + 59 = 123, are on different seeds)
    rows += _rows("b2_vrptw", {(i, s): (v, 0) for s, (x, y) in enumerate(((60, 59), (64, 55), (60, 56), (60, 57),
                                                                           (60, 58))) for i, v in (("I1", x), ("I2", y))},
                  host="host-A")
    rows += _rows("b3_mip", {("I1", 0): (72, 0)}, host="host-A")          # B3 runs on I1 only (like S only)
    # best of baselines: I1 max(70, 40, 64, 72) = 72, I2 max(50, 30, 59) = 59 -> 131
    rows += _five("e_above", (141, 150, 145, 160, 142))
    rows += _five("e_equal", (140, 150, 150, 150, 150))
    rows += _five("e_below", (132, 135, 170, 170, 170))
    rows += _five("e_four", (200, 200, 200, 200))
    rows += _five("e_partial", (200, 200, 200, 200, 200), missing={("I2", 4)})
    rows += _five("e_six", (200, 200, 200, 200, 200, 200), missing={("I2", 5)})    # 5 complete + 1 partial
    rows += _five("noop", (60, 60, 60, 60, 60))
    rows += _five("e_above", (150, 150, 150, 150, 150), host="host-B")         # another host: never pooled
    return rows


def _obs(host, delivered, source, method="b2_vrptw", budget=60.0):
    return {"set": "dev", "budget_s": budget, "method": method, "host": host, "delivered_checked": delivered,
            "source": source}


def test_bar_for_beating_b2_and_verdicts():
    """bar = max(B2 best observed: the best B2 per-seed total covering every instance, or a recorded observation
    of the same set, budget and host; best-of-baselines total: the per-instance best of any baseline, summed);
    a method beats B2 only with >= 5 repeats, each covering every instance, whose worst total exceeds the bar."""
    from evacplan.harness import compare_to_b2, render_leaderboard
    rows = _bar_fixture()
    observations = [_obs("host-A", 140, "fixture review"), _obs("host-B", 999, "review on host-B"),
                    _obs("host-A", 999, "review at 30 s", budget=30.0), _obs("host-A", 999, "review of B1", method="b1_greedy")]
    cmp = compare_to_b2(rows, ("I1", "I2"), set_name="dev", budget=60.0, host="host-A", observations=observations)
    assert cmp.best_of_baselines_total == cmp.best_of_baselines_rows == 131
    assert cmp.b2_best_observed == 140 and cmp.b2_source == "recorded (this host): fixture review"
    assert cmp.bar == 140
    assert cmp.verdicts == {
        "b0_independent": "baseline", "b1_greedy": "baseline", "b2_vrptw": "baseline", "b3_mip": "baseline",
        "e_above": "beats B2", "e_equal": "no (worst 140 ≤ bar 140)", "e_below": "no (worst 132 ≤ bar 140)",
        "e_four": "n/a (fewer than 5 repeats or not all instances)",
        "e_partial": "n/a (fewer than 5 repeats or not all instances)",
        "e_six": "n/a (fewer than 5 repeats or not all instances)", "noop": "–"}
    text = render_leaderboard(rows, _split(("I1", "I2"), residents=150), observations=observations)
    a = _sections(text)["## dev, budget 60 s, host host-A"]
    assert ("Bar for beating B2 on this host: max(B2 best observed 140 [recorded (this host): fixture review], "
            "best-of-baselines total 131 [this host's baseline rows]) = 140; a method beats B2 only if its worst of ≥5 "
            "repeats exceeds 140 and none of its rows is over the budget.") in a
    assert ("Recorded B2 observation for this set and budget from this host (not in the rows; "
            "`docs/recorded_observations.json`): 140 delivered [fixture review].") in a
    lines = a.splitlines()
    for method, verdict in cmp.verdicts.items():
        assert f"| {verdict} |" in next(x for x in lines if x.startswith(f"| {method} |")), method
    assert "fixture review" in a and "999" not in a
    assert not any(x in a for x in ("review on host-B", "review at 30 s", "review of B1"))
    # without a recorded observation for this host the B2 rows give X = 119 (seeds 0 and 1), and the bar is the
    # best-of-baselines total, 131: e_below's worst repeat, 132, now beats it
    cmp = compare_to_b2(rows, ("I1", "I2"), set_name="dev", budget=60.0, host="host-A",
                        observations=[_obs("host-B", 999, "review on host-B")])
    assert (cmp.b2_best_observed, cmp.best_of_baselines_total, cmp.bar) == (119, 131, 131)
    assert cmp.b2_source == "B2 rows on this host, seeds 0, 1"
    assert cmp.verdicts["e_below"] == cmp.verdicts["e_equal"] == cmp.verdicts["e_above"] == "beats B2"
    # host-B has no baseline rows and no recorded B2 total: no bar, nothing is judged
    cmp = compare_to_b2(rows, ("I1", "I2"), set_name="dev", budget=60.0, host="host-B", observations=[])
    assert cmp.bar is None and cmp.best_of_baselines_total is None and cmp.b2_best_observed is None
    assert cmp.verdicts == {"e_above": "n/a (no bar on this host)"}
    b = _sections(render_leaderboard(rows, _split(("I1", "I2"), residents=150), observations=[]))[
        "## dev, budget 60 s, host host-B"]
    assert "Bar for beating B2 on this host: undefined" in b and "| e_above | SYNTHETIC | 2 | 5 | 150 (50.0%) |" in b


def _margin_case(*, fire, horizon):
    """A 1 x 5 lattice (100 m cells, 50 s edges): depot n0_0, facility F at n0_1 (10 s boarding per resident),
    shelter S at n0_3 (5 s unloading). One vehicle, two trips: 2 residents unloaded over [170, 180], then 3 over
    [410, 425]. ``fire``: the depot cell ignites at 265 s; the approach last touches it at t = 25 (the cell
    boundary), so that leg's slack is 240 s and no later leg touches the cell."""
    from evacplan_testkit import (board, drive, facility, grid_graph, instance, itinerary, make_set, nid, path, quiet,
                                  shelter, solution, unload, vehicle)
    ig = quiet(1, 5)
    if fire:
        ig[0, 0, 0] = 265.0
    inst = instance(grid_graph(1, 5), facilities=[facility("F", nid(0, 1), amb=5)], vehicles=[vehicle("V", nid(0, 0))],
                    shelters=[shelter("S", nid(0, 3))])
    plan = itinerary("V", drive(path((0, 0), (0, 1)), 0), board("F", 2), drive(path((0, 1), (0, 2), (0, 3)), 70),
                     unload("S", 2), drive(path((0, 3), (0, 2), (0, 1)), 180), board("F", 3),
                     drive(path((0, 1), (0, 2), (0, 3)), 310), unload("S", 3))
    return inst, make_set(ig, horizon=horizon), solution(plan)


@pytest.mark.parametrize("fire, horizon, legs, slacks, curve", [
    # prefix rule: trip 2's own legs have at least 600 s, but the approach of trip 1 (240 s) comes first
    (True, 1025.0, [240, 955, 905, 855, 845, 795, 745, 715, 665, 615, 600], [(240.0, 2), (240.0, 3)],
     {0: 5, 1: 5, 2: 5, 5: 0, 10: 0, 15: 0, 20: 0, 30: 0, 45: 0, 60: 0}),
    # horizon cap: nothing burns, every leg's slack is horizon - leg end; trip 1 ends at 180, trip 2 at 425
    (False, 1100.0, [1050, 1030, 980, 930, 920, 870, 820, 790, 740, 690, 675], [(920.0, 2), (675.0, 3)],
     {0: 5, 1: 5, 2: 5, 5: 5, 10: 5, 15: 2, 20: 0, 30: 0, 45: 0, 60: 0}),
    # trip 2 runs past the horizon: unresolved, never delivered, not in any margin column
    (False, 400.0, [350, 330, 280, 230, 220, 170, 120, 90, 40, None, None], [(220.0, 2)],
     {0: 2, 1: 2, 2: 2, 5: 0, 10: 0, 15: 0, 20: 0, 30: 0, 45: 0, 60: 0}),
])
def test_margin_columns_on_a_hand_built_plan(fire, horizon, legs, slacks, curve):
    """A delivered resident's safety slack = the minimum oracle leg slack over their vehicle's legs from the start of
    the itinerary through the unloading that delivers them (the prefix rule of min_slack_s, ASSUMPTIONS #27), each
    leg capped at horizon - leg end. delivered_slack_ge_0m equals delivered_checked."""
    from evacplan.harness import delivered_by_margin, delivered_slacks
    inst, ss, sol = _margin_case(fire=fire, horizon=horizon)
    plan = Oracle(inst, ss).check_plan(sol)
    assert [lg.slack_s for lg in plan.vehicles[0].legs] == legs                # the oracle's own leg slacks
    assert delivered_slacks(plan) == slacks
    assert delivered_by_margin(plan) == curve
    assert curve[0] == plan.delivered_total == sum(n for _, n in slacks)
    assert plan.unresolved_total == 5 - plan.delivered_total
    assert plan.min_slack_s == min(s for s, _ in slacks)                      # consistent with the plan's min slack

    class Entry:
        id, generator, generator_version, config, fingerprint, label = inst.name, "hand", "0", {}, "none", "SYNTHETIC"
    row = make_row(entry=Entry, set_name="dev", method_name="hand", method_config={}, seed=0, budget_s=60.0, plan=plan,
                   runtime_s=0.0, best_bound=None, commit="c", host="h")
    assert row["delivered_slack_ge_0m"] == row["delivered_checked"] == str(plan.delivered_total)
    assert [row[f"delivered_slack_ge_{m}m"] for m in (5, 15, 30)] == [str(curve[m]) for m in (5, 15, 30)]
    assert json.loads(row["config"])["delivered_by_margin_min"] == {str(m): n for m, n in curve.items()}
    with pytest.raises(ValueError, match="slack"):                 # the columns must agree with delivered_checked
        make_row(entry=Entry, set_name="dev", method_name="hand", method_config={}, seed=0, budget_s=60.0, plan=plan,
                 runtime_s=0.0, best_bound=None, commit="c", host="h", margins={**curve, 0: curve[0] + 1})


def test_slack_ge_0_equals_delivered_on_random_plans():
    """On random plans (every state, many validator issues, zero-count unloadings): residents delivered with slack
    >= 0 = delivered_checked, the curve never increases with the margin, and no delivered resident has less slack
    than the plan's min_slack_s (equal when every checked trip carries residents)."""
    from evacplan.harness import MARGINS_MIN, delivered_by_margin, delivered_slacks
    from evacplan_testkit import random_case
    delivering = 0
    for seed in range(5000, 5080):
        inst, ss, sol = random_case(seed)
        plan = Oracle(inst, ss).check_plan(sol)
        curve = delivered_by_margin(plan)
        assert tuple(curve) == MARGINS_MIN and curve[0] == plan.delivered_total, seed
        assert all(curve[a] >= curve[b] for a, b in zip(MARGINS_MIN, MARGINS_MIN[1:])), seed
        pairs = delivered_slacks(plan)
        if pairs:
            delivering += 1
            assert min(s for s, _ in pairs) >= plan.min_slack_s >= 0, seed
            if all(t.counts.total for v in plan.vehicles for t in v.trips if t.state is State.CHECKED):
                assert min(s for s, _ in pairs) == plan.min_slack_s, seed
    assert delivering >= 5


def _png_text(path):
    """tEXt / zTXt / iTXt chunks of a PNG file."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    out, pos = {}, 8
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"tEXt":
            k, v = body.split(b"\0", 1)
            out[k.decode("latin-1")] = v.decode("latin-1")
        elif kind == b"zTXt":
            k, v = body.split(b"\0", 1)
            out[k.decode("latin-1")] = zlib.decompress(v[1:]).decode("latin-1")
        elif kind == b"iTXt":
            k, rest = body.split(b"\0", 1)
            compressed, rest = rest[0], rest[2:]
            _lang, rest = rest.split(b"\0", 1)
            _tkey, v = rest.split(b"\0", 1)
            out[k.decode("latin-1")] = (zlib.decompress(v) if compressed else v).decode("utf-8")
        pos += 12 + n
    return out


def test_margin_figure_is_written_and_says_synthetic(tmp_path):
    """Figure smoke: residents delivered vs required margin, one line per method (median over seeds) with a min-max
    band; the title says SYNTHETIC and names the host; small, deterministic PNG."""
    from evacplan.harness import margin_curves, write_margin_figure
    outcomes = {(i, s): (50, 0) for i in ("I1", "I2") for s in range(5)}
    margins = {(i, s): _curve(50, m10=40 - s, m20=30 - 2 * s, m30=20, m45=10, m60=0) for (i, s) in outcomes}
    rows = _rows("b1_greedy", outcomes, host="host-A", margins=margins)
    rows += _rows("noop", {k: (0, 0) for k in outcomes}, host="host-A")
    curves = margin_curves(rows)
    assert set(curves) == {"b1_greedy"}                                # noop is plumbing: not drawn
    c = curves["b1_greedy"]
    assert (c["instances"], c["seeds"]) == (2, 5)
    assert c["median"][MARGINS.index(10)] == 76 and (c["lo"][MARGINS.index(20)], c["hi"][MARGINS.index(20)]) == (44, 60)
    path = tmp_path / "figures" / "margin.png"
    title = write_margin_figure(rows, path, set_name="dev", budget=60.0, host="host-A")
    assert "SYNTHETIC" in title and "host-A" in title and "dev" in title and "60 s" in title
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) < 200_000
    assert _png_text(path)["Title"] == title
    write_margin_figure(rows, path, set_name="dev", budget=60.0, host="host-A")
    assert path.read_bytes() == data                                   # deterministic


def test_leaderboard_links_the_margin_figure_and_the_cli_regenerates_it(tmp_path):
    from evacplan.harness import figure_name
    write_split(_split(("I1", "I2")), tmp_path / "SPLIT.json")
    results = tmp_path / "results"
    upsert_rows(results / "b1_greedy.csv",
                _rows("b1_greedy", {(i, s): (50, 0) for i in ("I1", "I2") for s in range(5)}, host="host-A"))
    board = tmp_path / "board" / "LEADERBOARD.md"
    board.parent.mkdir()
    args = ["leaderboard", "--split", str(tmp_path / "SPLIT.json"), "--results-dir", str(results),
            "--leaderboard", str(board)]
    assert main(args) == 0
    fig = board.parent / "figures" / figure_name("dev", 60.0, "host-A")
    assert fig.is_file() and fig.name.startswith("margin_dev_60s_host-a")
    assert f"(figures/{fig.name})" in board.read_text()
    fig.unlink()
    assert main(args) == 0 and fig.is_file()                           # `evacplan leaderboard` regenerates it


def test_old_schema_rows_are_read_and_render_dashes(tmp_path):
    """Rows written before 2026-11-01 (no margin columns, the old host string) are read; the new columns render as
    "–"; an upsert rewrites the file with the new columns and keeps the old rows."""
    from evacplan.harness import render_leaderboard
    old_host = "vm (Linux x86_64, 4 cpu, python 3.12.3)"
    old = []
    for r in _rows("b1_greedy", {("I1", 0): (70, 0), ("I2", 0): (50, 0)}, host=old_host):
        cfg = json.loads(r["config"])
        del cfg["delivered_by_margin_min"]
        old.append({**{c: r[c] for c in OLD_COLUMNS}, "config": json.dumps(cfg, sort_keys=True, separators=(",", ":"))})
    path = tmp_path / "b1_greedy.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OLD_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(old)
    rows = read_rows(path)
    assert [r["delivered_checked"] for r in rows] == ["70", "50"]
    assert all(r[f"delivered_slack_ge_{m}m"] == "" for r in rows for m in (0, 5, 15, 30))
    text = render_leaderboard(rows, _split(("I1", "I2")), observations=[])
    line = next(x for x in text.splitlines() if x.startswith("| b1_greedy |"))
    assert line.startswith("| b1_greedy | SYNTHETIC | 2 | 1 | 120 (60.0%) | 0 |") and "| – | – | – |" in line
    assert f"## dev, budget 60 s, host {old_host}" in text and "no rows with margin columns" in text
    upsert_rows(path, _rows("b1_greedy", {("I1", 1): (70, 0)}, host=old_host))
    header, back = rows_of(path)
    assert tuple(header) == COLUMNS and len(back) == 3


def test_cli_repeats_runs_seeds_0_to_n_minus_1(mini):
    root, split = mini
    p = paths(root, "repeats")
    common = ["--split", str(p["split_path"]), "--cache-dir", str(p["cache_dir"]), "--results-dir",
              str(p["results_dir"]), "--leaderboard", str(p["leaderboard_path"])]
    assert main(["run", "--method", "noop", "--set", "dev", "--budget-s", "60", "--repeats", "5", "--lock", "no",
                 *common]) == 0
    assert sorted({r["seed"] for r in read_rows(p["results_dir"] / "noop.csv")}) == ["0", "1", "2", "3", "4"]
    with pytest.raises(SystemExit):                                    # --repeats or --seeds, not both
        main(["run", "--method", "noop", "--set", "dev", "--budget-s", "60", "--repeats", "5", "--seeds", "1",
              "--lock", "no", *common])
    with pytest.raises(SystemExit):
        main(["run", "--method", "noop", "--set", "dev", "--budget-s", "60", "--repeats", "0", "--lock", "no", *common])


def test_recorded_observation_of_the_phase0_review():
    """The Phase 0 review's B2 run (1750 delivered on dev at 60 s, not in the rows) is a recorded observation keyed
    by set, budget, method and the cloud machine's host string, with its source."""
    from evacplan.harness import RECORDED_OBSERVATIONS_PATH, load_recorded_observations
    assert RECORDED_OBSERVATIONS_PATH.is_file()
    (o,) = [o for o in load_recorded_observations() if (o.set, o.budget_s, o.method) == ("dev", 60.0, "b2_vrptw")]
    assert o.delivered_checked == 1750 and "phase0-review.md" in o.source and "957e6720" in o.source
    assert "Intel(R) Xeon(R) Processor @ 2.80GHz" in o.host and "python 3.12.3" in o.host
    from evacplan.harness import host_class
    assert host_class(o.host) == o.host                 # recorded for the host class: every session of the cloud VM


def test_recorded_observation_of_a_host_class_applies_to_every_session_of_it():
    """An observation recorded under a host class (a VM host string without its boot session) raises the bar in the
    table of every session of that class: it can only make beating B2 harder. One recorded under a session applies to
    that session only; one of another class never applies."""
    from evacplan.harness import compare_to_b2
    cls = "vm (Linux x86_64, Intel(R) Xeon(R) Processor @ 2.80GHz, 4 cpu, python 3.12.3)"
    a, b = cls[:-1] + ", vm boot aaaa1111)", cls[:-1] + ", vm boot bbbb2222)"
    other = "mac (Darwin arm64, Apple M2 Pro, 10 cpu, python 3.12.3)"

    def row(host, method, inst, seed, n):
        return {"instance": inst, "method": method, "seed": str(seed), "delivered_checked": str(n), "host": host,
                "config": json.dumps({"set": "dev", "budget_s": 60.0})}

    def obs(host, n):
        return {"set": "dev", "budget_s": 60.0, "method": "b2_vrptw", "host": host, "delivered_checked": n,
                "source": "test"}
    rows = [row(h, m, i, 0, n) for h in (a, b) for m, n in (("b1_greedy", 10), ("b2_vrptw", 12)) for i in ("x", "y")]
    observations = [obs(cls, 30), obs(a, 40), obs(other, 99)]
    ca = compare_to_b2(rows, ["x", "y"], set_name="dev", budget=60, host=a, observations=observations)
    cb = compare_to_b2(rows, ["x", "y"], set_name="dev", budget=60, host=b, observations=observations)
    assert (ca.best_of_baselines_total, ca.b2_best_observed, ca.bar) == (24, 40, 40)      # class 30 and session 40
    assert (cb.best_of_baselines_total, cb.b2_best_observed, cb.bar) == (24, 30, 30)      # class only
    assert {o.delivered_checked for o in ca.recorded} == {30, 40} and {o.delivered_checked for o in cb.recorded} == {30}
    cc = compare_to_b2(rows, ["x", "y"], set_name="dev", budget=60, host=cls, observations=[obs(a, 40)])
    assert cc.b2_best_observed is None                   # a session's observation never applies to the class table
    assert cb.b2_source == "recorded (an earlier session of this host class): test"


def test_a_recorded_observation_never_defines_a_bar_on_its_own():
    """A recorded B2 total or best-of-baselines total only raises a bar that the table's own rows define. In a
    session where B2 never ran, or where an instance has no baseline row, there is no bar and nothing beats B2,
    however good (batch-1 review, harness D3; docs/ASSUMPTIONS.md #92-#93)."""
    from evacplan.harness import compare_to_b2, render_leaderboard
    cls = "vm (Linux x86_64, Intel(R) Xeon(R) Processor @ 2.80GHz, 4 cpu, python 3.12.3)"
    s = cls[:-1] + ", vm boot 12345678)"
    observations = [_obs(cls, 125, "class B2"), _obs(cls, 126, "class best of baselines", method="best_of_baselines")]
    rows = _rows("b1_greedy", {(i, 0): (v, 0) for i, v in (("I1", 60), ("I2", 40))}, host=s)
    rows += _five("e_good", (180, 180, 180, 180, 180), host=s)
    cmp = compare_to_b2(rows, ("I1", "I2"), set_name="dev", budget=60.0, host=s, observations=observations)
    assert cmp.b2_best_observed is None and cmp.best_of_baselines_total == 126 and cmp.bar is None
    assert cmp.verdicts["e_good"] == "n/a (no bar on this host)"
    assert [cmp.used(o) for o in cmp.recorded] == [False, True]
    text = _sections(render_leaderboard(rows, _split(("I1", "I2")), observations=observations))[
        f"## dev, budget 60 s, host {s}"]
    assert ("Bar for beating B2 on this host: undefined (no B2 per-seed total covering all 2 instances on this host; "
            "best-of-baselines total 126; a recorded observation only raises a bar that this host's own rows define); "
            "no method is judged against B2 here.") in text
    assert ("Recorded B2 observation for this set and budget from an earlier session of this host class (not in the "
            "rows; `docs/recorded_observations.json`; not used: this host's own rows define no bar): 125 delivered "
            "[class B2].") in text
    # once B2 has a seed covering every instance in this session, both observations raise the bar
    rows += _rows("b2_vrptw", {(i, 0): (v, 0) for i, v in (("I1", 58), ("I2", 42))}, host=s)
    cmp = compare_to_b2(rows, ("I1", "I2"), set_name="dev", budget=60.0, host=s, observations=observations)
    assert (cmp.b2_best_observed, cmp.best_of_baselines_rows, cmp.best_of_baselines_total, cmp.bar) == (125, 102, 126, 126)
    assert cmp.bob_source == ("this host's baseline rows 102; recorded (an earlier session of this host class): "
                              "class best of baselines")
    assert cmp.verdicts["e_good"] == "beats B2"
    # a baseline row missing on one instance leaves the best-of-baselines total, and so the bar, undefined
    partial = [r for r in rows if not (r["method"] in ("b1_greedy", "b2_vrptw") and r["instance"] == "I2")]
    cmp = compare_to_b2(partial, ("I1", "I2"), set_name="dev", budget=60.0, host=s, observations=observations)
    assert cmp.best_of_baselines_total is None and cmp.bar is None


def test_rows_over_the_budget_get_no_verdict():
    """Equal wall-clock budgets (program rule 6): a method with any row whose runtime exceeded the budget is not
    judged against B2, whatever it delivered (batch-1 review, harness D4)."""
    from evacplan.harness import compare_to_b2, render_leaderboard
    rows = _bar_fixture()
    slow = _five("e_slow", (200, 200, 200, 200, 200))
    slow[3]["runtime_s"] = "60.0100"
    late = _five("e_late", (200, 200, 200, 200, 200))
    on_time = _five("e_on_time", (200, 200, 200, 200, 200))
    for r in late:
        r["runtime_s"] = "600.0000"
    for r in on_time:
        r["runtime_s"] = "60.0000"                        # exactly the budget is within it
    rows += slow + late + on_time
    cmp = compare_to_b2(rows, ("I1", "I2"), set_name="dev", budget=60.0, host="host-A")
    assert cmp.verdicts["e_slow"] == "n/a (1 row over the budget)"
    assert cmp.verdicts["e_late"] == "n/a (10 rows over the budget)"
    assert cmp.verdicts["e_on_time"] == "beats B2"
    a = _sections(render_leaderboard(rows, _split(("I1", "I2"), residents=150), observations=[]))[
        "## dev, budget 60 s, host host-A"]
    line = next(x for x in a.splitlines() if x.startswith("| e_late |"))
    assert "| 10 |" in line and "| n/a (10 rows over the budget) |" in line


def test_recorded_best_of_baselines_total_of_the_earlier_session():
    """Siyeong's checkpoint-2 rule asks a method's worst of 5 to exceed B2's best observed (1750) and the
    best-of-baselines total (1751) on dev at 60 s. The 1751 came from rows of an earlier session of the cloud VM
    (b43990bb, B2 517 on SYNTHETIC-L-grid-t50-s109) and is recorded for the host class (batch-1 review, harness D5)."""
    from evacplan.harness import compare_to_b2, host_class, load_recorded_observations
    obs = load_recorded_observations()
    (bob,) = [o for o in obs if (o.set, o.budget_s, o.method) == ("dev", 60.0, "best_of_baselines")]
    assert bob.delivered_checked == 1751 and "b43990bb" in bob.source and host_class(bob.host) == bob.host
    (b2,) = [o for o in obs if (o.set, o.budget_s, o.method) == ("dev", 60.0, "b2_vrptw")]
    assert b2.host == bob.host
    session = bob.host[:-1] + ", vm boot ff671362)"
    ids = [f"SYNTHETIC-{x}" for x in ("S-grid-t25-s101", "S-geo-t25-s102", "S-grid-t75-s103", "S-geo-t75-s104",
                                       "M-grid-t25-s105", "M-geo-t25-s106", "M-grid-t75-s107", "M-geo-t75-s108",
                                       "L-grid-t50-s109", "L-geo-t50-s110")]
    best = dict(zip(ids, (23, 37, 23, 26, 163, 155, 140, 139, 516, 528)))         # this session's rows: 1750
    b2_vals = dict(best, **{"SYNTHETIC-S-geo-t25-s102": 36})                      # B2: 1749 in every seed
    rows = _rows("b2_vrptw", {(i, s): (b2_vals[i], 0) for i in ids for s in range(5)}, host=session)
    rows += _rows("b1_greedy", {(i, 0): (best[i], 0) for i in ids}, host=session)
    for worst, verdict in ((1751, "no (worst 1751 ≤ bar 1751)"), (1752, "beats B2")):
        cand = _rows("e_x", {(i, s): (best[i] + (worst - 1750 if i == ids[-1] else 0), 0) for i in ids
                             for s in range(5)}, host=session)
        cmp = compare_to_b2(rows + cand, ids, set_name="dev", budget=60.0, host=session, observations=obs)
        assert (cmp.b2_best_observed, cmp.best_of_baselines_rows, cmp.best_of_baselines_total, cmp.bar) == \
            (1750, 1750, 1751, 1751)
        assert cmp.verdicts["e_x"] == verdict


# ------------------------------------------------------------------ bound-only methods (E4)
def _bound_rows(method, bounds, budget=600.0, host="h", runtime="12.5000"):
    """Rows of a bound-only method: empty plan (0 delivered), ``best_bound`` per instance, ``bound_only`` in the
    config, empty gap (as :func:`make_row` writes them)."""
    out = _rows(method, {(i, 0): (0, 0) for i in bounds}, budget=budget, host=host)
    for r in out:
        cfg = json.loads(r["config"])
        cfg["bound_only"] = True
        r["config"] = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
        r["best_bound"], r["runtime_s"] = f"{bounds[r['instance']]:.3f}", runtime
    return out


def test_make_row_marks_bound_only_rows_and_leaves_their_gap_empty(mini):
    from evacplan.harness import is_bound_only
    root, split = mini
    p = paths(root, "bound-only")
    (row,) = run("noop", "dev", 5, instances=[split.ids("dev")[0]], lock="no", log=lambda s: None, **p)
    entry = split.entries("dev")[0]
    inst = load_instance(p["cache_dir"] / entry.id / "instance.json")
    plan = Oracle(inst, load_scenario_set(inst)).check_plan(Solution(instance=inst.name, itineraries=[]))
    common = dict(entry=entry, set_name="dev", method_name="e4_flow_bound", method_config={}, seed=0, budget_s=600.0,
                  plan=plan, runtime_s=3.0, best_bound=21.0, commit="c", host="h")
    b = make_row(**common, bound_only=True)
    assert is_bound_only(b) and b["best_bound"] == "21.000" and b["gap"] == "" and b["delivered_checked"] == "0"
    n = make_row(**common)
    assert not is_bound_only(n) and n["gap"] == "1.000000" and not is_bound_only(row)


def test_bound_only_rows_feed_the_best_bound_and_their_own_table_not_the_totals():
    """A bound-only method computed at another budget joins the 60 s table of its set and host: its bound is the
    best bound where it is the smallest, it has its own table with runtime and gap to the best plan, and it gets no
    row in the method table, no verdict and no line in the margin figure."""
    from evacplan.harness import compare_to_b2, margin_curves, render_leaderboard
    split = _split(("I1", "I2"))
    rows = _rows("b2_vrptw", {(i, s): (d, 0) for s in range(5) for i, d in (("I1", 90), ("I2", 70))})
    rows += _rows("b1_greedy", {("I1", 0): (95, 0), ("I2", 0): (60, 0)})
    b3 = _rows("b3_mip", {("I1", 0): (95, 0)})
    b3[0]["best_bound"], b3[0]["gap"] = "99.000", "0.040404"
    rows += b3 + _bound_rows("e4_flow_bound", {"I1": 97, "I2": 80})
    text = render_leaderboard(rows, split, observations=[])
    assert list(_sections(text)) == ["## dev, budget 60 s, host h"]          # no table of its own at 600 s
    methods = _table(text, "| method |")
    assert not any(x.startswith("| e4_flow_bound |") for x in methods)
    assert any(x.startswith("| b2_vrptw |") for x in methods)
    delivered = _table(text, "Delivered (checked) per instance")
    head = [c.strip() for c in delivered[0].strip("|").split("|")]
    assert "e4_flow_bound" not in head
    best = head.index("best bound")
    cells = {x.split("|")[1].strip(): [c.strip() for c in x.strip("|").split("|")] for x in delivered[2:]}
    assert cells["I1"][best] == "97" and cells["I2"][best] == "80"        # min(99, 97) and 80
    bounds = _table(text, "Proven upper bounds of bound-only methods")
    assert bounds[0].startswith("| instance | label | residents | best delivered | e4_flow_bound | gap | runtime (s) |")
    assert next(x for x in bounds if x.startswith("| I1 |")) == "| I1 | SYNTHETIC | 100 | 95 | 97 | 2.1% | 12.5 |"
    assert next(x for x in bounds if x.startswith("| I2 |")) == "| I2 | SYNTHETIC | 100 | 70 | 80 | 12.5% | 12.5 |"
    assert "Mean gap of e4_flow_bound by size (instances): M 7.3% (2), all 7.3% (2); computed at budget 600 s" in text
    assert "INVALID" not in text
    cmp = compare_to_b2(rows, ["I1", "I2"], set_name="dev", budget=60.0, host="h")
    assert "e4_flow_bound" not in cmp.verdicts and cmp.best_of_baselines_total == 95 + 70
    assert "e4_flow_bound" not in margin_curves([r for r in rows if r["host"] == "h"])


def test_a_bound_below_a_delivered_plan_is_flagged_invalid_and_bounds_alone_get_a_section():
    from evacplan.harness import render_leaderboard
    split = _split(("I1",))
    rows = _rows("b1_greedy", {("I1", 0): (95, 0)}) + _bound_rows("e4_flow_bound", {"I1": 94})
    text = render_leaderboard(rows, split, observations=[])
    assert "**INVALID BOUND**" in text and "e4_flow_bound on I1: bound 94 < delivered 95" in text
    alone = render_leaderboard(_bound_rows("e4_flow_bound", {"I1": 94}, host="other"), split, observations=[])
    (head,) = _sections(alone)
    assert head == "## dev, budget 600 s, host other"
    assert "No plans for this set, budget and host" in alone and "| I1 | SYNTHETIC | 100 | – | 94 | – | 12.5 |" in alone


def test_harness_runs_the_bound_only_method_end_to_end(mini):
    """``evacplan run --method e4_flow_bound``: rows say bound_only, carry a proven bound at least as large as
    every plan of the same instances (B1 here), and the leaderboard has the bounds table."""
    root, split = mini
    p = paths(root, "e4")
    b1 = run("b1_greedy", "dev", 30, lock="no", log=lambda s: None, **p)
    e4 = run("e4_flow_bound", "dev", 120, lock="no", log=lambda s: None, **p)
    by = {r["instance"]: r for r in e4}
    assert set(by) == set(split.ids("dev"))
    for r in b1:
        e = by[r["instance"]]
        assert json.loads(e["config"])["bound_only"] is True and e["gap"] == "" and e["delivered_checked"] == "0"
        assert int(r["delivered_checked"]) <= float(e["best_bound"])
    text = p["leaderboard_path"].read_text()
    assert "Proven upper bounds of bound-only methods" in text
    assert not any(x.startswith("| e4_flow_bound |") for x in text.splitlines())      # no method row


# ------------------------------------------------------------- batch 2: certification time, interleaved holds
def test_every_row_records_a_cold_final_certification_time(mini):
    """Final certification stays outside the budget, but its time is recorded (config certify_s) so the leaderboard
    can show time to a certified plan = runtime + certification (program/DECISIONS.md, 2026-11-02)."""
    root, split = mini
    p = paths(root, "certify")
    rows = run("b0_independent", "dev", 5, seeds=[0], lock="no", log=lambda s: None, **p)
    assert rows and all(float(row_config(r)["certify_s"]) >= 0 for r in rows)
    text = p["leaderboard_path"].read_text()
    assert "| time to certified plan (s) |" in text and "slack ≥ 30 min (default)" in text
    line = next(x for x in text.splitlines() if x.startswith("| b0_independent |"))
    want = sum(float(r["runtime_s"]) + float(row_config(r)["certify_s"]) for r in rows) / len(rows)
    assert f"| {want:.1f} |" in line


def test_interleaved_hold_alternates_b2_and_the_challenger_with_a_speed_check(mini):
    """ABAB in one lock hold: for every instance and seed, a speed probe, then the partner, then the challenger. The
    partner's seeds continue after its earlier rows, so a second hold adds repeats and replaces none."""
    root, split = mini
    p = paths(root, "interleave")
    ids = split.ids("dev")
    first = run("noop", "dev", 5, seeds=[0, 1], interleave_with="b0_independent", lock="no", log=lambda s: None, **p)
    assert [r["method"] for r in first] == ["b0_independent", "noop"] * (len(ids) * 2)
    assert [(r["instance"], int(r["seed"])) for r in first[::2]] == [(i, s) for i in ids for s in (0, 1)]
    cfgs = [row_config(r) for r in first]
    hold = cfgs[0]["hold"]
    assert all(c["hold"] == hold and c["certify_s"] >= 0 and c["speed_probe_s"] > 0 for c in cfgs)
    assert [c["pair"] for c in cfgs[::2]] == [c["pair"] for c in cfgs[1::2]] == [f"{i}/{s}" for i in ids for s in (0, 1)]
    second = run("noop", "dev", 5, seeds=[0, 1], interleave_with="b0_independent", lock="no", log=lambda s: None, **p)
    assert sorted({int(r["seed"]) for r in second if r["method"] == "b0_independent"}) == [2, 3]
    b0 = rows_of(p["results_dir"] / "b0_independent.csv")[1]
    assert sorted({int(r["seed"]) for r in b0}) == [0, 1, 2, 3]                # both holds' repeats are kept
    speed = speed_rows(p["results_dir"])
    assert len(speed) == 2 * len(ids) * 2 and {r["hold"] for r in speed} == {hold, row_config(second[0])["hold"]}
    text = p["leaderboard_path"].read_text()
    assert "Interleaved holds" in text and text.count("| speed check (s) |") == 2
    with pytest.raises(ValueError):
        run("noop", "dev", 5, seeds=[0], interleave_with="noop", lock="no", log=lambda s: None, **p)


def test_partner_seeds_are_shared_by_holds_on_disjoint_instances_and_never_replaced(mini):
    """Holds on disjoint instances (S+M, then L in batch 2) give the partner the same seeds, so its per-seed totals
    cover every instance; a later hold on the same instances continues after them; an explicit offset that would
    replace a partner row is refused (program/DECISIONS.md 2026-11-02)."""
    root, split = mini
    p = paths(root, "offsets")
    a, b = split.ids("dev")
    kw = dict(p, leaderboard_path=None, interleave_with="b0_independent", lock="no", log=lambda s: None)
    seeds_of = lambda rows: sorted((r["instance"], int(r["seed"])) for r in rows if r["method"] == "b0_independent")
    assert seeds_of(run("noop", "dev", 5, seeds=[0, 1], instances=[a], **kw)) == [(a, 0), (a, 1)]
    assert seeds_of(run("noop", "dev", 5, seeds=[0, 1], instances=[b], **kw)) == [(b, 0), (b, 1)]
    assert seeds_of(run("noop", "dev", 5, seeds=[0], **kw)) == sorted([(a, 2), (b, 2)])
    with pytest.raises(ValueError, match="replaces none"):
        run("noop", "dev", 5, seeds=[0, 1], instances=[b], partner_seed_offset=1, **kw)
    assert seeds_of(run("noop", "dev", 5, seeds=[0], instances=[b], partner_seed_offset=5, **kw)) == [(b, 5)]
    b0 = rows_of(p["results_dir"] / "b0_independent.csv")[1]
    assert sorted((r["instance"], int(r["seed"])) for r in b0) == sorted([
        (a, 0), (a, 1), (a, 2), (b, 0), (b, 1), (b, 2), (b, 5)])
