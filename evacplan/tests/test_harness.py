"""The harness: CSV schema, upserts, the leaderboard, the test-set guard, oracle-only scoring and
the bench lock. Runs on a throw-away split of SYNTHETIC instances (seeds 9301-9303, outside the
frozen split) in temporary folders."""
import csv
import json
import os
import socket
import subprocess
import sys
import textwrap

import pytest

from evacplan import Board, ClassCounts, Itinerary, Oracle, Solution, load_instance, load_scenario_set
from evacplan.cli import main
from evacplan.generators import SyntheticConfig
from evacplan.harness import (
    COLUMNS, FACILITY_COLUMNS, TestSetRefused, bench_guard, load_benchlock, lock_held_by_ancestor, make_row,
    read_rows, run,
)
from evacplan.instances import build_split, write_split
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
    root, split = mini
    p = paths(root, "schema")
    out = run("noop", "dev", 60, seeds=[0, 1], lock="no", log=lambda s: None, **p)
    assert len(out) == 4
    header, rows = rows_of(p["results_dir"] / "noop.csv")
    assert tuple(header) == COLUMNS == ("instance", "method", "seed", "delivered_checked", "unresolved",
                                        "model_no_route", "makespan_s", "min_slack_s", "runtime_s", "best_bound",
                                        "gap", "commit", "config", "host")
    fps = {e.id: e.fingerprint for e in split.entries("dev")}
    assert sorted((r["instance"], r["seed"]) for r in rows) == sorted((i, s) for i in fps for s in ("0", "1"))
    for r in rows:
        assert r["method"] == "noop" and r["delivered_checked"] == r["unresolved"] == r["model_no_route"] == "0"
        assert r["makespan_s"] == r["min_slack_s"] == r["best_bound"] == r["gap"] == ""
        assert 0 <= float(r["runtime_s"]) < 60 and r["commit"] and r["host"]
        cfg = json.loads(r["config"])
        assert cfg["set"] == "dev" and cfg["budget_s"] == 60.0 and cfg["method"] == {} and cfg["label"] == "SYNTHETIC"
        assert cfg["instance"]["fingerprint"] == fps[r["instance"]] and cfg["instance"]["config"]["seed"] in (9301, 9302)
        assert cfg["oracle"] and cfg["hazard_contract"]
    plans = sorted((p["results_dir"] / "runs" / "noop" / "dev-b60").glob("*.result.json"))
    assert len(plans) == 4 and json.loads(plans[0].read_text())["label"] == "SYNTHETIC"


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
    assert "## dev, budget 30 s" in text and "## dev, budget 60 s" in text
    assert "| noop | SYNTHETIC | 2 | 2 | 0 (0.0%) |" in text and "| noop | SYNTHETIC | 1 | 1 | 0 (0.0%) |" in text
    assert all(i in text for i in split.ids("dev")) and not any(i in text for i in split.ids("test"))
    assert "**SYNTHETIC** rows are SYNTHETIC instances" in text and "equal wall-clock budgets" in text
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
              runtime_s=1.0, commit="c", host="h")
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
