"""The RELAXED check (never a final state) and ground rule 3 (only evacplan.oracle declares states)."""
import ast
import re
import textwrap
from pathlib import Path

import numpy as np
import pytest

from evacplan import RelaxedContactCheck, RelaxedItinerary, RelaxedLeg, State
from evacplan_testkit import NAN, drive, grid_graph, instance, itinerary, make_set, nid, path, quiet, vehicle, wait

SRC = Path(__file__).resolve().parents[1] / "src" / "evacplan"

# ------------------------------------------------------------------ the rule-3 guard (syntax tree)
DECLARING = frozenset({"State", "LegResult", "ActionResult", "TripResult", "ItineraryResult", "PlanResult",
                       "ClassDeadline"})
BUILDERS = frozenset({"model_validate", "model_validate_json", "model_validate_strings", "model_construct",
                      "model_copy", "parse_obj", "parse_raw", "construct", "copy"})
STATE_FIELDS = frozenset({"state", "hazard_state", "dose_state", "probe_state"})
COMPARISONS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn, ast.Is, ast.IsNot)


def rule3_offenders(source: str, filename: str = "<sample>") -> list[str]:
    """Program rule 3 on the syntax tree: outside evacplan.oracle, code may read states but not declare them.

    Flagged: constructing ``State`` or an oracle result (``LegResult``, ``ActionResult``, ``TripResult``,
    ``ItineraryResult``, ``PlanResult``, ``ClassDeadline``), also through pydantic builders on those classes
    (``model_validate``, ``model_copy``, ...); ``model_copy``/``copy`` of any model with a state field in its
    update (or an update that is not a literal, which cannot be told apart); ``State[...]`` and
    ``getattr(State, ...)``; and any use of ``State.<member>`` other than as an operand of ``==``, ``!=``,
    ``in``, ``not in``, ``is``, ``is not`` (directly, or inside a literal tuple, list or set compared with
    ``in`` / ``not in``) or as a ``case`` pattern. Import aliases (``from .oracle import State as S``) and
    module attributes (``oracle.State``) count."""
    tree = ast.parse(source, filename)
    parent: dict[ast.AST, ast.AST] = {}
    alias: dict[str, str] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name in DECLARING:
                    alias[a.asname or a.name] = a.name

    def declaring(node) -> str | None:
        if isinstance(node, ast.Name):
            return alias.get(node.id, node.id if node.id in DECLARING else None)
        if isinstance(node, ast.Attribute) and node.attr in DECLARING:
            return node.attr
        return None

    def compared(node) -> bool:
        up = parent.get(node)
        if isinstance(up, (ast.Tuple, ast.List, ast.Set)):
            node, up = up, parent.get(up)
            return (isinstance(up, ast.Compare) and node in up.comparators
                    and all(isinstance(op, (ast.In, ast.NotIn)) for op in up.ops))
        if isinstance(up, ast.MatchValue):
            return True
        return isinstance(up, ast.Compare) and all(isinstance(op, COMPARISONS) for op in up.ops)

    def state_update(call: ast.Call) -> bool:
        for kw in call.keywords:
            if kw.arg != "update":
                continue
            v = kw.value
            if isinstance(v, ast.Dict):
                return any(not isinstance(k, ast.Constant) or k.value in STATE_FIELDS for k in v.keys)
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "dict" and not v.args:
                return any(k.arg is None or k.arg in STATE_FIELDS for k in v.keywords)
            return True
        return False

    out: list[str] = []
    for node in ast.walk(tree):
        where = f"{filename}:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.Call):
            f = node.func
            if declaring(f):
                out.append(f"{where}: constructs {declaring(f)}")
            elif isinstance(f, ast.Attribute) and f.attr in BUILDERS and declaring(f.value):
                out.append(f"{where}: builds {declaring(f.value)} with .{f.attr}()")
            elif isinstance(f, ast.Attribute) and f.attr in ("model_copy", "copy") and state_update(node):
                out.append(f"{where}: copies a model with a state field in its update")
            elif isinstance(f, ast.Name) and f.id == "getattr" and node.args and declaring(node.args[0]) == "State":
                out.append(f"{where}: looks up a State member with getattr")
        elif isinstance(node, ast.Subscript) and declaring(node.value) == "State":
            out.append(f"{where}: looks up a State member by name")
        elif isinstance(node, ast.Attribute) and declaring(node.value) == "State" and not compared(node):
            out.append(f"{where}: uses State.{node.attr} outside a comparison")
    return sorted(set(out))


def checker(ig, **kw):
    ss = make_set(ig, **kw)
    inst = instance(grid_graph(3, 3), vehicles=[vehicle("V", nid(1, 0))])
    return RelaxedContactCheck(inst, ss)


def test_relaxed_legs():
    ig = quiet(3, 3)
    ig[0, 1, 1] = 50.0
    ig[0, 0, 0] = NAN
    rc = checker(ig, horizon=1000.0)
    e = path((1, 0), (1, 1))[0]                 # in the middle cell during [25, 50] after departure
    assert rc.traverse(e, 0.0) == RelaxedLeg(blocked=True, uncertain=False)
    assert rc.traverse(e, -30.0) == RelaxedLeg(blocked=False, uncertain=False)
    assert rc.stay(nid(0, 0), 0.0, 10.0) == RelaxedLeg(blocked=False, uncertain=True)   # unknown: not blocked
    assert rc.stay(nid(2, 2), 990.0, 1001.0) == RelaxedLeg(blocked=False, uncertain=True)


def test_relaxed_itinerary_stops_at_the_first_blocked_leg_and_lists_issues():
    ig = quiet(3, 3)
    ig[0, 1, 1] = 0.0
    rc = checker(ig)
    it = itinerary("V", wait(nid(1, 0), 5.0), drive(path((1, 0), (1, 1), (1, 2)), 5.0), wait(nid(2, 2), 1.0))
    out = rc.itinerary(it)
    assert isinstance(out, RelaxedItinerary)
    assert out.first_blocked == 1 and len(out.legs) == 2
    full = rc.itinerary(it, stop_at_block=False)
    assert len(full.legs) == 4 and [c.code for c in full.issues] == ["WRONG_LOCATION"]


def test_relaxed_results_carry_no_final_state():
    rc = checker(quiet(3, 3))
    leg = rc.stay(nid(1, 1), 0.0, 1.0)
    out = rc.itinerary(itinerary("V", wait(nid(1, 0), 1.0)))
    for obj in (leg, out):
        assert not isinstance(obj, State)
        assert not any(isinstance(v, State) for v in vars(obj).values())
        assert "state" not in vars(obj)


def test_only_the_oracle_declares_final_states():
    """Program rule 3: no module but evacplan.oracle may declare states or oracle results (reading them is fine)."""
    offenders = []
    for f in sorted(SRC.rglob("*.py")):
        if f.name != "oracle.py":
            offenders += rule3_offenders(f.read_text(), str(f.relative_to(SRC)))
    assert not offenders, offenders
    assert rule3_offenders((SRC / "oracle.py").read_text(), "oracle.py")     # the guard does flag the oracle itself


# the regex this guard replaces, and the six declarations it missed (Phase 0 review, C-m2)
OLD_REGEX = re.compile(r"State\(|=\s*State\.|\b(LegResult|ActionResult|TripResult|ItineraryResult|PlanResult)\(")
REGEX_MISSED = [
    "def f():\n    return State.CHECKED",
    "d = ClassDeadline(state=st)",
    "table = {'a': State.UNRESOLVED}",
    "states = [State.CHECKED for _ in items]",
    "p = PlanResult.model_validate(d)",
    "r2 = res.model_copy(update={'state': s})",
]
DECLARES = REGEX_MISSED + [
    "s = State('checked')",
    "x = State.CHECKED",
    "f(state=State.MODEL_NO_ROUTE)",
    "import evacplan.oracle as o\nr = o.TripResult(**kw)",
    "from evacplan.oracle import State as S\ndef f():\n    return S.CHECKED",
    "from evacplan.oracle import ClassDeadline as CD\nd = CD.model_construct(**kw)",
    "y = State['CHECKED']",
    "z = getattr(State, 'CHECKED')",
    "r = res.model_copy(update=changes)",
    "r = res.model_copy(update=dict(probe_state=s))",
    "q = LegResult.model_validate_json(raw)",
    "v = State.CHECKED.value",
    "if a < State.CHECKED:\n    pass",
]
READS = [
    "if r.state is State.CHECKED:\n    pass",
    "ok = x.state == State.UNRESOLVED",
    "bad = s in (State.CHECKED, State.UNRESOLVED)",
    "good = s not in {State.MODEL_NO_ROUTE}",
    "n = a.state != State.CHECKED",
    "bad = next((t for t in trips if t.state is not State.CHECKED), None)",
    "sol = res.solution.model_copy(update={'provenance': {}})",
    "cfg2 = cfg.model_copy(update={'tightness': 1.0})",
    "v = t.state.value",
    "from evacplan.oracle import State, PlanResult\ndef f(s: State) -> list[PlanResult]:\n    return []",
    "match s:\n    case State.CHECKED:\n        pass",
    "text = 'State(checked) and PlanResult(...) in a string'",
]


def test_the_old_regex_missed_these():
    assert not any(OLD_REGEX.search(s) for s in REGEX_MISSED)


@pytest.mark.parametrize("code", DECLARES)
def test_rule3_guard_flags_declarations(code):
    assert rule3_offenders(textwrap.dedent(code)), code


@pytest.mark.parametrize("code", READS)
def test_rule3_guard_allows_reading_states(code):
    assert rule3_offenders(textwrap.dedent(code)) == []
