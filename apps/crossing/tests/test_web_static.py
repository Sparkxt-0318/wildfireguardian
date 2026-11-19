"""Static and served checks of the crossing web UI (apps/crossing/web/, DESIGN.md section 9).

What is checked here (no browser, no network):
- the files exist; the import map maps ``three`` and ``three/addons/`` to the vendored r180 files; the sha256 table
  in ``web/vendor/README.md`` matches the files (and the source copy in ``demos/showcase/vendor/``);
- nothing is loaded from the network: no http(s) or protocol-relative URL in our HTML/JS/CSS, and every import in
  our modules and in the vendored modules resolves to a vendored file;
- every State path the UI reads (``web/js/fields.js``) exists in States produced by ``crossing.pipeline`` on
  SYNTHETIC sessions (``hardware/vehicle-unit/samples/flame_front`` and ``tests/test_pipeline.build_session``), is
  documented in README STATE_SCHEMA, and the UI reads the State only through those paths;
- text colour pairs in ``web/css/app.css`` meet WCAG AA (4.5:1) in light and dark themes;
- the app serves the page and every asset with the right media type (FastAPI TestClient, no port);
- when ``node`` is installed: ``web/js/model.js`` (the browser-side fail-closed verdict logic) is run on those
  States: a fresh State shows the app's verdict, a stale / missing / malformed / expired one shows CLOSED.

Not checked here: rendering in a real browser (WebGL), layout, or the three.js scene itself.
"""
import functools
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from crossing import pipeline as pl
from crossing.config import load_config

ROOT = Path(__file__).resolve().parents[1]          # apps/crossing
REPO = ROOT.parents[1]
WEB = ROOT / "web"
VENDOR = WEB / "vendor"
SAMPLE = REPO / "hardware" / "vehicle-unit" / "samples" / "flame_front"
OWN_JS = ["app.js", "fields.js", "model.js", "panel.js", "scene.js"]
VENDOR_FILES = ["three/three.module.js", "three/three.core.js", "three/addons/controls/OrbitControls.js",
                "three/THREE-LICENSE.txt"]
NODE = shutil.which("node")


def read(p):
    return Path(p).read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------------- files, vendor
def test_files_exist():
    for rel in ["index.html", "css/app.css", "vendor/README.md"] + ["js/" + f for f in OWN_JS] + \
               ["vendor/" + f for f in VENDOR_FILES]:
        assert (WEB / rel).is_file(), rel


def import_map():
    html = read(WEB / "index.html")
    m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
    assert m, "no import map"
    return json.loads(m.group(1))["imports"]


def test_import_map_points_to_vendored_files():
    imports = import_map()
    assert imports["three"] == "./vendor/three/three.module.js"
    assert imports["three/addons/"] == "./vendor/three/addons/"
    for spec, target in imports.items():
        assert target.startswith("./vendor/three/"), (spec, target)
        p = (WEB / target).resolve()
        assert p.exists(), target
        assert WEB.resolve() in p.parents
    core = read(VENDOR / "three/three.core.js")
    assert "REVISION = '180'" in core


def test_vendor_sha256_matches_readme_and_source():
    table = dict(re.findall(r"^\|\s*(three/[^|\s]+)\s*\|\s*([0-9a-f]{64})\s*\|", read(VENDOR / "README.md"), re.M))
    assert set(table) == set(VENDOR_FILES)
    src = REPO / "demos" / "showcase" / "vendor"
    for rel in VENDOR_FILES:
        digest = hashlib.sha256((VENDOR / rel).read_bytes()).hexdigest()
        assert digest == table[rel], rel
        s = src / rel.split("/", 1)[1]
        if s.exists():
            assert hashlib.sha256(s.read_bytes()).hexdigest() == digest, "differs from %s" % s


# --------------------------------------------------------------------------------------------- no network
URL_RE = re.compile(r"(https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IMPORT_RE = re.compile(r"""(?:^|[;\s])import\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)""", re.M)


def own_text_files():
    return [WEB / "index.html", WEB / "css/app.css"] + [WEB / "js" / f for f in OWN_JS]


def test_no_network_urls_in_own_files():
    for p in own_text_files():
        t = read(p)
        assert "http://" not in t and "https://" not in t, p
        assert not URL_RE.search(t.replace("location.host", "")), (p, URL_RE.search(t).group(0))
    css = read(WEB / "css/app.css")
    assert "@import" not in css and "url(" not in css
    html = read(WEB / "index.html")
    for attr in re.findall(r'\b(?:src|href)="([^"]+)"', html):
        assert not re.match(r"^[a-z]+:|^//", attr), attr
        assert (WEB / attr).is_file(), attr


def resolve_spec(spec, base: Path):
    imports = import_map()
    if spec.startswith("./") or spec.startswith("../"):
        return (base.parent / spec).resolve()
    if spec in imports:
        return (WEB / imports[spec]).resolve()
    for prefix, target in imports.items():
        if prefix.endswith("/") and spec.startswith(prefix):
            return (WEB / target / spec[len(prefix):]).resolve()
    raise AssertionError("bare or remote import %r in %s" % (spec, base))


def test_every_module_import_resolves_locally():
    files = [WEB / "js" / f for f in OWN_JS] + [VENDOR / "three/three.module.js", VENDOR / "three/three.core.js",
                                                  VENDOR / "three/addons/controls/OrbitControls.js"]
    seen = 0
    for p in files:
        for m in IMPORT_RE.finditer(read(p)):
            spec = m.group(1) or m.group(2)
            target = resolve_spec(spec, p)
            assert target.is_file(), (p, spec)
            assert WEB.resolve() in target.parents, (p, spec)
            seen += 1
    assert seen >= 8
    # three.js is only reached through the dynamic import of scene.js, so the panel survives a failed 3D load
    app = read(WEB / "js/app.js") + read(WEB / "js/panel.js") + read(WEB / "js/model.js")
    assert '"three' not in app and "'three" not in app
    assert 'import("./scene.js")' in read(WEB / "js/app.js")


# --------------------------------------------------------------------------------------------- State fields
def fields():
    t = read(WEB / "js/fields.js")
    block = t[t.index("export const F = {"):]
    block = block[:block.index("};")]
    f = dict(re.findall(r'^\s*(\w+):\s*"([^"]+)",', block, re.M))
    sensors = json.loads(re.search(r"export const SENSORS = (\[.*?\]);", t).group(1))
    return f, sensors


_MISSING = object()


def lookup(state, path):
    """Values at a fields.js path (expanded over list elements); _MISSING if a key is absent."""
    p = path.rstrip("?")
    if "[]." in p:
        head, tail = p.split("[].", 1)
        lst = lookup(state, head)
        if not isinstance(lst, list) or not lst:
            return _MISSING
        vals = [lookup(e, tail) for e in lst]
        return _MISSING if any(v is _MISSING for v in vals) else vals
    o = state
    for k in p.split("."):
        if not isinstance(o, dict) or k not in o:
            return _MISSING
        o = o[k]
    return o


def expand(path, sensors):
    return [path.replace("{sensor}", s) for s in sensors] if "{sensor}" in path else [path]


def _cfg(tmp):
    return load_config(overrides={"paths": {"records_dir": str(tmp), "pairs_path": str(tmp / "p.jsonl"),
                                            "sim_pairs_path": str(tmp / "ps.jsonl")}})


@functools.lru_cache(maxsize=1)
def sample_states():
    """(name, [states]) of two SYNTHETIC runs: the committed flame_front sample (fire_engine, placeholder limits ->
    CLOSED DOSE_OVER_LIMIT) and the in-test generator with the test-only vehicle (-> CROSS FAST)."""
    import tempfile

    import test_pipeline as tp
    tmp = Path(tempfile.mkdtemp(prefix="webstatic_"))
    runs = []
    if SAMPLE.is_dir() and list(SAMPLE.glob("*.jsonl.gz")):
        pipe = pl.Pipeline(_cfg(tmp / "a"), "fire_engine", "DEFAULT", mode="replay", source=str(SAMPLE))
        st = pl.run_virtual(pipe, pl.iter_source(SAMPLE), hooks={6.0: lambda p, now: p.capture_baseline(now)})
        runs.append(("sample_flame_front", [s for _, s in st]))
    from crossing.simlink import SimLinkClient
    # with a (never started) sim-link client: replay + simulated data, so it is disabled; its status is in the State
    pipe = pl.Pipeline(_cfg(tmp / "b"), tp.TEST_VEHICLE, "DEFAULT", mode="replay", source="synthetic",
                       simlink=SimLinkClient("ws://127.0.0.1:1/v1/live/closures", "test_region", mode="replay"))
    hello, msgs = tp.build_session("flame_front", duration=16.0)
    st = pl.run_virtual(pipe, tp.items_of(hello, msgs), hooks=tp.capture_at(4.5))
    runs.append(("generator_cross_fast", [s for _, s in st]))
    shutil.rmtree(tmp, ignore_errors=True)
    return runs


def reference_states():
    """Fully populated States: FLAME with a valid depth (one per run)."""
    out = []
    for name, states in sample_states():
        good = [s for s in states if s.get("flame", {}).get("status") == "FLAME" and s.get("depth", {}).get("valid")
                and s.get("heat", {}).get("valid") and s.get("geometry", {}).get("valid")]
        assert good, name
        out.append((name, good[-1]))
    return out


def test_sample_runs_cover_closed_and_cross_fast():
    seen = {s["verdict"]["state"] for _, states in sample_states() for s in states}
    assert {"CLOSED", "CROSS FAST"} <= seen, seen


def test_every_ui_field_exists_in_pipeline_states():
    f, sensors = fields()
    assert sensors == ["thermal", "radar", "tc_plate", "tc_housing", "tc_air", "imu", "gnss", "pi"]
    all_states = [s for _, states in sample_states() for s in states]
    refs = reference_states()
    for key, path in f.items():
        for p in expand(path, sensors):
            assert any(lookup(s, p) is not _MISSING for s in all_states), "%s = %s never present" % (key, p)
            if not path.endswith("?"):
                for name, ref in refs:
                    assert lookup(ref, p) is not _MISSING, "%s = %s missing in %s" % (key, p, name)


def test_every_ui_field_is_documented_in_state_schema():
    f, _ = fields()
    readme = read(ROOT / "README.md")
    schema = readme[readme.index("## STATE_SCHEMA"):]
    schema = schema[:schema.index("\n## ", 5)]
    for key, path in f.items():
        parts = [x for x in path.rstrip("?").replace("[]", "").split(".") if x != "{sensor}"]
        # verdict.details is documented as an open dict of decision details (decision.py); only "details" is named
        check = ("details",) if path.startswith("verdict.details.") else (parts[0], parts[-1])
        for part in check:
            assert re.search(r"\b%s\b" % re.escape(part), schema), "%s (%s) not in README STATE_SCHEMA" % (part, path)


def test_ui_reads_state_only_through_fields():
    f, _ = fields()
    used = set()
    for name in OWN_JS:
        if name == "fields.js":
            continue
        t = read(WEB / "js" / name)
        assert not re.search(r"\bsv\(\s*\w+\s*,\s*['\"]", t), "%s: raw path string in sv()" % name
        assert not re.search(r"\bel\(\s*\w+\s*,\s*['\"]", t), "%s: raw path string in el()" % name
        assert not re.search(r"\b(state|s)\??\.[a-z_]+\b(?!\()", t), "%s: direct State property access" % name
        assert not re.search(r"\[['\"](verdict|health|flame|geometry|depth|flux|heat|gnss|vehicle|fuel)['\"]\]", t), name
        used |= set(re.findall(r"\bF\.(\w+)", t))
    assert used <= set(f), sorted(used - set(f))
    assert set(f) <= used, "fields.js lists paths the UI never reads: %s" % sorted(set(f) - used)


# --------------------------------------------------------------------------------------------- contrast
CONTRAST_PAIRS = [
    ("--fg", "--bg"), ("--fg", "--panel-bg"), ("--fg", "--card-bg"), ("--muted", "--bg"), ("--muted", "--panel-bg"),
    ("--muted", "--card-bg"), ("--banner-fg", "--banner-bg"), ("--closed-fg", "--closed-bg"), ("--go-fg", "--go-bg"),
    ("--spray-fg", "--spray-bg"), ("--reopen-fg", "--reopen-bg"), ("--ok-fg", "--card-bg"), ("--bad-fg", "--card-bg"),
    ("--warn-fg", "--card-bg"), ("--placeholder-fg", "--card-bg"), ("--bad-fg", "--panel-bg"),
    ("--sim-badge-fg", "--sim-badge-bg"), ("--button-fg", "--button-bg"), ("--button2-fg", "--button2-bg"),
    ("--fg", "--card-bg"),
]
# labels float over the 3D scene: check them over every scene colour they can overlap
LABEL_UNDER = ["--scene-bg", "--scene-ground", "--scene-road", "--scene-vehicle", "--scene-flame", "--scene-flame-int",
               "--scene-flame-front", "--scene-near", "--scene-echo"]


def css_themes():
    css = read(WEB / "css/app.css")
    blocks = re.findall(r":root\s*\{(.*?)\}", css, re.S)
    light = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", blocks[0]))
    dark = dict(light)
    dark.update(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", blocks[1]))
    assert "prefers-color-scheme: dark" in css
    return {"light": light, "dark": dark}


def rgba(v):
    v = v.strip()
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.match(r"rgba?\(([^)]*)\)", v)
    assert m, v
    p = [x.strip() for x in m.group(1).split(",")]
    return (int(p[0]), int(p[1]), int(p[2]), float(p[3]) if len(p) > 3 else 1.0)


def over(top, under):
    a = top[3]
    return tuple(top[i] * a + under[i] * (1 - a) for i in range(3)) + (1.0,)


def lum(c):
    def ch(x):
        x = x / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_contrast_wcag_aa(theme):
    v = css_themes()[theme]
    bad = []
    for fg, bg in CONTRAST_PAIRS:
        c = contrast(rgba(v[fg]), over(rgba(v[bg]), (255, 255, 255, 1.0)))
        if c < 4.5:
            bad.append((fg, bg, round(c, 2)))
    for under in LABEL_UNDER:
        bgc = over(rgba(v["--label-bg"]), rgba(v[under]))
        c = contrast(rgba(v["--label-fg"]), bgc)
        if c < 4.5:
            bad.append(("--label-fg", "--label-bg over " + under, round(c, 2)))
    assert not bad, bad


def test_verdicts_have_text_not_colour_alone():
    m = read(WEB / "js/model.js")
    for st, cls in (("CLOSED", "v-closed"), ("CROSS FAST", "v-go"), ("SPRAY THEN RE-CHECK", "v-spray"),
                    ("REOPENED", "v-reopen")):
        assert re.search(r'"%s":\s*\{\s*cls:\s*"%s",\s*glyph:\s*"[^"]+",\s*say:\s*"[^"]+"' % (st, cls), m), st
    css = read(WEB / "css/app.css")
    for cls, var in (("v-closed", "closed"), ("v-go", "go"), ("v-spray", "spray"), ("v-reopen", "reopen")):
        assert ".%s { background: var(--%s-bg); color: var(--%s-fg); }" % (cls, var, var) in css
    html = read(WEB / "index.html")
    for text in ("Advisory for trained crews", "PLACEHOLDER limit: set by fire service", "SIMULATED",
                 "FDS C064 reference", "Slope source", "Capture radar baseline", "Mark crossing"):
        assert text in html, text


# --------------------------------------------------------------------------------------------- served
def test_served_by_the_app(tmp_path):
    from fastapi.testclient import TestClient

    from crossing.server import Runtime, create_app
    pipe = pl.Pipeline(_cfg(tmp_path), "fire_engine", "DEFAULT", mode="idle")
    with TestClient(create_app(Runtime(pipe), start_tasks=False)) as c:
        r = c.get("/")
        assert r.status_code == 200 and r.text == read(WEB / "index.html")
        assets = ["css/app.css"] + ["js/" + f for f in OWN_JS] + ["vendor/" + f for f in VENDOR_FILES[:3]]
        for a in assets:
            r = c.get("/" + a)
            assert r.status_code == 200, a
            assert r.content == (WEB / a).read_bytes(), a
            ctype = r.headers["content-type"]
            if a.endswith(".js"):
                assert ctype.startswith(("text/javascript", "application/javascript")), (a, ctype)
            else:
                assert ctype.startswith("text/css"), (a, ctype)
        with c.websocket_connect("/ws") as ws:
            st = json.loads(ws.receive_text())
        assert st["schema"] == "crossing.state/1" and st["verdict"]["state"] == "CLOSED"
        for route in ("/api/vehicles", "/api/fuels", "/api/state"):
            assert c.get(route).status_code == 200, route


# --------------------------------------------------------------------------------------------- model.js in node
NODE_SCRIPT = r"""
const m = await import(process.argv[1] + "/model.js");
const { F } = await import(process.argv[1] + "/fields.js");
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = {};
for (const [name, st] of Object.entries(input.states)) {
  const r = {};
  for (const c of input.clients) r[c.name] = m.shownVerdict(st, c);
  r.paths = {};
  for (const [k, p] of Object.entries(F)) {
    if (p.includes("[]") || p.includes("{sensor}")) continue;
    const v = m.sv(st, p);
    r.paths[k] = v === undefined ? "__undef__" : v;
  }
  r.health = m.healthLights(st);
  out[name] = r;
}
out.nostate = m.shownVerdict(null, { hasState: false, wsOpen: true, sinceRxS: 0 });
out.fmt = [m.fmt(null), m.fmt(1.234, 2, "m"), m.fmtRange(1, null, 1, "m"), m.fmt(NaN)];
process.stdout.write(JSON.stringify(out));
"""


def run_node(payload, tmp: Path):
    """Runs NODE_SCRIPT on copies of model.js and fields.js in a folder marked "type": "module" (our files have no
    package.json, and node treats bare .js as CommonJS)."""
    d = tmp / "jsmod"
    d.mkdir()
    (d / "package.json").write_text('{"type": "module"}')
    for name in ("model.js", "fields.js"):
        shutil.copy(WEB / "js" / name, d / name)
    script = "import { createRequire } from 'module'; const require = createRequire(import.meta.url);\n" + NODE_SCRIPT
    p = subprocess.run([NODE, "--input-type=module", "-e", script, d.as_uri()], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_browser_verdict_logic_fails_closed(tmp_path):
    refs = dict(reference_states())
    cross = refs["generator_cross_fast"]
    assert cross["verdict"]["state"] == "CROSS FAST"
    expired = json.loads(json.dumps(cross))
    expired["verdict"]["age_s"] = 5.2                         # app pushed it 5.2 s after issue (should not happen)
    bad_schema = dict(cross, schema="crossing.state/0")
    bad_verdict = json.loads(json.dumps(cross))
    bad_verdict["verdict"]["state"] = "GO"
    no_timing = json.loads(json.dumps(cross))
    del no_timing["verdict"]["expires_mono"]
    minimal = {k: cross[k] for k in ("schema", "sim", "mode", "source", "advisory", "verdict")}
    minimal["verdict"] = dict(cross["verdict"], state="CLOSED", reasons=["LINK_DOWN"])
    states = dict(refs, expired=expired, bad_schema=bad_schema, bad_verdict=bad_verdict, no_timing=no_timing,
                  minimal=minimal)
    clients = [{"name": "fresh", "hasState": True, "wsOpen": True, "sinceRxS": 0.1},
               {"name": "near_expiry", "hasState": True, "wsOpen": True, "sinceRxS": 1.9},
               {"name": "stale", "hasState": True, "wsOpen": True, "sinceRxS": 2.01},
               {"name": "socket_closed", "hasState": True, "wsOpen": False, "sinceRxS": 0.1},
               {"name": "no_clock", "hasState": True, "wsOpen": True, "sinceRxS": None}]
    out = run_node({"states": states, "clients": clients}, tmp_path)

    fresh = out["generator_cross_fast"]["fresh"]
    assert fresh["state"] == "CROSS FAST" and not fresh["override"]
    assert 0 < fresh["expiresInS"] <= 5.0
    assert out["sample_flame_front"]["fresh"]["state"] == refs["sample_flame_front"]["verdict"]["state"]
    for name in states:
        for c in ("stale", "socket_closed", "no_clock"):
            assert out[name][c]["state"] == "CLOSED" and out[name][c]["override"], (name, c)
    for name in ("expired", "bad_schema", "bad_verdict", "no_timing"):
        for c in ("fresh", "near_expiry"):
            assert out[name][c]["state"] == "CLOSED" and out[name][c]["override"], (name, c, out[name][c])
    assert out["minimal"]["fresh"]["state"] == "CLOSED" and not out["minimal"]["fresh"]["override"]
    assert all(not h["ok"] and h["label"] == "NO DATA" for h in out["minimal"]["health"])
    assert out["nostate"]["state"] == "CLOSED" and out["nostate"]["codes"] == ["UI_NO_STATE"]
    assert out["fmt"] == ["—", "1.23 m", "1.0–∞ m", "—"]

    # sv() in the browser agrees with the Python reading of the same paths
    f, _ = fields()
    for name, ref in refs.items():
        got = out[name]["paths"]
        for k, v in got.items():
            exp = lookup(ref, f[k])
            assert v == ("__undef__" if exp is _MISSING else exp), (name, k)
        lights = {h["name"]: h["ok"] for h in out[name]["health"]}
        assert lights == {k: v["fresh"] is True for k, v in ref["health"]["sensors"].items()}


# --------------------------------------------------------------------------------------------- wording, reasons
OWN_TEXT = ["index.html", "css/app.css"] + ["js/" + f for f in OWN_JS]


def test_no_readiness_claims_and_advisory_placeholder_wording():
    """The page never claims operational readiness (no field test has run), says "advisory for trained crews" and
    labels every limit it prints as a PLACEHOLDER."""
    banned = re.compile(r"operational(ly)?\s+ready|readiness|ready\s+for|production[- ]ready|certified|"
                        r"validated|guarantee|safe\s+to\s+cross|field[- ]tested|fire[- ]service\s+approved", re.I)
    for rel in OWN_TEXT:
        m = banned.search(read(WEB / rel))
        assert m is None, (rel, m.group(0) if m else None)
    html = read(WEB / "index.html")
    assert "Advisory for trained crews" in html
    assert "PLACEHOLDER limit: set by fire service" in html and "PLACEHOLDER limits: to be set by the fire service" in html
    panel = read(WEB / "js/panel.js")
    assert "Advisory for trained crews" in panel and "Not verified on hardware" in panel
    # every limit the panel prints carries the PLACEHOLDER label in the same statement
    stmts = re.split(r";\s*\n", panel)
    for key in ("vehMaxSpeed", "vehIntakeLimit", "reopenHold", "thermalTflame"):
        hits = [st for st in stmts if "F.%s)" % key in st]
        assert hits and all("PLACEHOLDER" in st for st in hits), key
    for code in ("DOSE_OVER_LIMIT", "DOSE_WITHIN_LIMIT", "INTAKE_AIR_OVER_LIMIT", "REOPEN_HOLD_NOT_MET",
                 "PLATE_FLUX_ABOVE_REOPEN"):
        line = re.search(r"^\s*%s:\s*\"([^\"]+)\"" % code, read(WEB / "js/model.js"), re.M)
        assert line and "PLACEHOLDER" in line.group(1), code


def test_simulated_and_replay_labels_present():
    html = read(WEB / "index.html")
    for ident in ('id="sim-badge"', 'id="sim-watermark"', 'id="verdict-sim"', 'id="verdict-action"'):
        assert ident in html, ident
    panel = read(WEB / "js/panel.js")
    assert '"SIMULATED DATA"' in panel and "REPLAY" in panel and "F.sim" in panel and "F.mode" in panel


RENDER_SCRIPT = r"""
// Minimal DOM stub: enough for panel.renderVerdict (no browser in the test environment).
const els = {};
function mk(tag) {
  return { tag, textContent: "", hidden: false, className: "", children: [], style: {},
           replaceChildren(...c) { this.children = c; }, append(...c) { this.children.push(...c); },
           setAttribute() {} };
}
globalThis.document = { getElementById: (id) => (els[id] = els[id] || mk("div")),
                        createElement: (t) => mk(t), createTextNode: (t) => ({ textContent: t }) };
const m = await import(process.argv[1] + "/model.js");
const p = await import(process.argv[1] + "/panel.js");
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const client = { hasState: true, wsOpen: true, sinceRxS: 0.1 };
const out = {};
for (const [name, st] of Object.entries(input.states)) {
  const v = p.renderVerdict(st, client);
  out[name] = { shown: v.state, override: v.override, actions: v.actions, reasons: v.reasons,
                box: els["verdict-state"].textContent, action: els["verdict-action"].textContent,
                actionHidden: els["verdict-action"].hidden, sim: els["verdict-sim"].textContent,
                simHidden: els["verdict-sim"].hidden,
                items: els["verdict-reasons"].children.map((li) => li.children.map((c) => c.textContent).join("")),
                unknownCls: els["verdict-reasons"].children.map((li) => li.className) };
}
out.text = input.codes.map((c) => [c, m.reasonText(c), m.reasonActions([c]), m.isKnownReason(c)]);
process.stdout.write(JSON.stringify(out));
"""


def run_node_render(payload, tmp: Path):
    d = tmp / "jsrender"
    d.mkdir()
    (d / "package.json").write_text('{"type": "module"}')
    for name in ("model.js", "fields.js", "panel.js"):
        shutil.copy(WEB / "js" / name, d / name)
    script = "import { createRequire } from 'module'; const require = createRequire(import.meta.url);\n" + RENDER_SCRIPT
    p = subprocess.run([NODE, "--input-type=module", "-e", script, d.as_uri()], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_new_and_unknown_reason_codes_render_and_never_go(tmp_path):
    """CLOSED reasons the decision module adds (REOPEN_CROSSING_NOT_IN_VIEW with the crew instruction to face the
    crossed road, NEAR_EDGE_NOT_OBSERVED, FLAME_EVIDENCE_TOO_SHORT) and codes this UI has never seen are shown
    generically; the shown verdict is the app's state (or the browser's CLOSED), never a go made from a reason."""
    refs = dict(reference_states())
    cross = refs["generator_cross_fast"]
    sample = refs["sample_flame_front"]

    def with_verdict(base, state, reasons, **top):
        s = json.loads(json.dumps(base))
        s["verdict"].update(state=state, reasons=reasons)
        s.update(top)
        return s

    new_codes = ["REOPEN_CROSSING_NOT_IN_VIEW", "NEAR_EDGE_NOT_OBSERVED", "FLAME_EVIDENCE_TOO_SHORT:1.2 s < 3.0 s"]
    weird = ["SOME_FUTURE_CODE:x", "GO", "CROSS FAST", "DOSE_WITHIN_LIMIT", "<b>html</b>", ""]
    states = {
        "closed_new": with_verdict(cross, "CLOSED", new_codes),
        "closed_weird": with_verdict(cross, "CLOSED", weird),
        "closed_renamed": with_verdict(cross, "CLOSED", ["REOPEN_ROAD_NOT_IN_VIEW", "NEAR_EDGE_NOT_SEEN",
                                                         "FLAME_NOT_PERSISTENT:2 frames"]),
        "bad_state_go_reasons": with_verdict(cross, "GO", ["DOSE_WITHIN_LIMIT", "SOME_FUTURE_CODE"]),
        "cross_fast_unknown": with_verdict(cross, "CROSS FAST", ["DOSE_WITHIN_LIMIT", "SOME_FUTURE_CODE"]),
        "replay_real": with_verdict(sample, "CLOSED", ["LINK_DOWN"], sim=False, mode="replay"),
        "live_real": with_verdict(sample, "CLOSED", ["LINK_DOWN"], sim=False, mode="live"),
        "sim_live": with_verdict(sample, "CLOSED", ["LINK_DOWN"], sim=True, mode="live"),
    }
    out = run_node_render({"states": states, "codes": new_codes + weird}, tmp_path)

    c = out["closed_new"]
    assert c["shown"] == "CLOSED" and c["box"] == "CLOSED" and not c["override"]
    assert not c["actionHidden"] and "Face the crossed road" in c["action"]
    assert "flame base" in c["action"] and "wait for a new verdict" in c["action"]
    assert c["unknownCls"] == ["", "", ""]
    assert any("1.2 s < 3.0 s" in x for x in c["items"])
    w = out["closed_weird"]
    assert w["shown"] == "CLOSED" and w["actionHidden"] and len(w["items"]) == len(weird)
    assert "code not known to this UI" in w["reasons"][0] and "some future code (x)" in w["reasons"][0]
    assert w["unknownCls"][0] == "unknown-reason" and w["unknownCls"][3] == ""
    r = out["closed_renamed"]
    assert r["shown"] == "CLOSED" and "Face the crossed road" in r["action"] and len(r["actions"]) == 3
    b = out["bad_state_go_reasons"]
    assert b["shown"] == "CLOSED" and b["override"]
    k = out["cross_fast_unknown"]                       # the app's go verdict is shown as sent; reasons only listed
    assert k["shown"] == "CROSS FAST" and "code not known to this UI" in k["reasons"][1] and k["actionHidden"]
    assert out["replay_real"]["sim"] == "REPLAY: recorded data, not live" and not out["replay_real"]["simHidden"]
    assert out["live_real"]["simHidden"]
    assert out["sim_live"]["sim"] == "SIMULATED DATA" and not out["sim_live"]["simHidden"]
    assert "SIMULATED" in out["closed_new"]["sim"]       # generator States are sim: true
    text = {c0: (t, a, known) for c0, t, a, known in out["text"]}
    assert text["REOPEN_CROSSING_NOT_IN_VIEW"][2] is True and text["REOPEN_CROSSING_NOT_IN_VIEW"][1]
    assert text["GO"][2] is False and text["GO"][1] == []


# --------------------------------------------------------------------------------------------- estimator table (R5)
def test_estimator_table_reads_depth_used_not_valid_alone():
    """R5: the table must not call every valid estimator "used"; it reads depth.used through fields.js."""
    panel = read(WEB / "js/panel.js")
    assert "used/valid" not in panel
    assert "F.depthUsed" in panel
    f, _ = fields()
    assert f["depthUsed"] == "depth.used"


ESTROWS_SCRIPT = r"""
globalThis.document = { getElementById: () => null, createElement: () => ({}), createTextNode: (t) => ({ textContent: t }) };
const p = await import(process.argv[1] + "/panel.js");
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = {};
for (const [name, st] of Object.entries(input.states)) out[name] = p.estimatorRows(st);
process.stdout.write(JSON.stringify(out));
"""


def run_node_estrows(payload, tmp: Path):
    d = tmp / "jsest"
    d.mkdir()
    (d / "package.json").write_text('{"type": "module"}')
    for name in ("model.js", "fields.js", "panel.js"):
        shutil.copy(WEB / "js" / name, d / name)
    script = "import { createRequire } from 'module'; const require = createRequire(import.meta.url);\n" + ESTROWS_SCRIPT
    p = subprocess.run([NODE, "--input-type=module", "-e", script, d.as_uri()], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_estimator_rows_say_used_only_for_depth_used(tmp_path):
    """R5 regression on the sample_flame_front States: flicker_extent (experimental, off by default) and radar_ceiling
    (untrusted ceiling) never render as "used"; the estimators in depth.used do. Missing depth.used or an invalid
    combined depth: no row says "used" (fail closed)."""
    refs = dict(reference_states())
    base = refs.get("sample_flame_front") or refs["generator_cross_fast"]
    states = {}
    for name, st in refs.items():
        states[name] = st
        no_used = json.loads(json.dumps(st))
        no_used["depth"].pop("used", None)
        states[name + "_no_used"] = no_used
        bad = json.loads(json.dumps(st))
        bad["depth"]["used"] = "byram"
        states[name + "_used_not_list"] = bad
        inv = json.loads(json.dumps(st))
        inv["depth"]["valid"] = False
        states[name + "_invalid"] = inv
    forced = json.loads(json.dumps(base))           # every estimator valid, only byram used
    for e in forced["depth"]["estimators"]:
        e.update(valid=True, value_m=e.get("value_m") or 3.0, lo_m=e.get("lo_m") or 2.0, hi_m=e.get("hi_m") or 5.0)
    forced["depth"]["used"] = ["byram"]
    states["forced_all_valid"] = forced
    out = run_node_estrows({"states": states}, tmp_path)

    def rows(name):
        return {r[0].split(" (")[0]: r[3] for r in out[name]}

    for name, st in refs.items():
        used = set(st["depth"]["used"])
        assert used, name
        r = rows(name)
        for e in st["depth"]["estimators"]:
            status = r[e["name"]]
            if e["valid"] and e["name"] in used:
                assert status == "used", (name, e["name"], status)
            else:
                assert status != "used", (name, e["name"], status)
        assert r["flicker_extent"] != "used" and r["radar_ceiling"] != "used", r
        for suffix in ("_no_used", "_used_not_list", "_invalid"):
            assert all(v != "used" for v in rows(name + suffix).values()), (name + suffix, rows(name + suffix))
    if "sample_flame_front" in refs:
        s = refs["sample_flame_front"]
        assert "byram" in s["depth"]["used"] and rows("sample_flame_front")["byram"] == "used"
    f = rows("forced_all_valid")
    assert f["byram"] == "used"
    assert f["flicker_extent"] == "valid, not used (experimental, off by default)"
    assert f["radar_ceiling"] == "valid, not used (ceiling; not trusted by calibration)"
    assert f["spread_burn"] == "valid, not used"


# --------------------------------------------------------------------------------------------- tick re-render (FS-10)
APP_TICK_SCRIPT = r"""
// Stubs: enough of the browser for app.js to load, connect a fake socket and run its 100 ms tick by hand.
let T = 0;
Object.defineProperty(globalThis, "performance", { value: { now: () => T }, configurable: true, writable: true });
const els = {};
function mk(id) {
  const o = { id, textContent: "", hidden: false, className: "", children: [], style: {}, value: "", options: [],
              disabled: false, width: 0, height: 0,
              replaceChildren(...c) { this.children = c; }, append(...c) { this.children.push(...c); },
              setAttribute() {}, addEventListener() {}, blur() {}, getContext() { return null; } };
  o.tBodies = [{ replaceChildren() {} }];
  return o;
}
globalThis.document = { getElementById: (id) => (els[id] = els[id] || mk(id)), createElement: (t) => mk(t),
                        createTextNode: (t) => ({ textContent: t }), activeElement: null };
globalThis.window = { confirm: () => false };
globalThis.location = { protocol: "http:", host: "127.0.0.1:8781", search: "?nowebgl" };
globalThis.fetch = async () => { throw new Error("no network in test"); };
let sock = null;
globalThis.WebSocket = class { constructor(url) { this.url = url; sock = this; } close() {} };
let tickFn = null;
globalThis.setInterval = (fn) => { tickFn = fn; return 1; };
globalThis.setTimeout = () => 0;
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
await import(process.argv[1] + "/app.js");
sock.onopen();
T = 0;
sock.onmessage({ data: JSON.stringify(input.state) });
const out = { fresh: { verdict: els["verdict-state"].textContent, minSpeed: els["min-speed"].textContent } };
// 2.5 s later with the socket still open and no new message: ticks 1..9 (none is the 1 Hz full render)
T = 2500;
tickFn();
out.stale = { verdict: els["verdict-state"].textContent, minSpeed: els["min-speed"].textContent,
              override: !els["verdict-override"].hidden };
process.stdout.write(JSON.stringify(out));
"""


def test_app_tick_rerenders_panel_when_shown_verdict_changes_static():
    app = read(WEB / "js/app.js")
    body = app[app.index("function tick()"):]
    body = body[:body.index("\n}\n")]
    assert "renderAll()" in body.replace("if (ticks % 10 === 0) { renderAll(); return; }", "")


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_app_tick_clears_min_speed_when_browser_forces_closed(tmp_path):
    """FS-10: a CROSS FAST State, then the State goes stale with the socket open. The first 100 ms tick after that
    shows CLOSED (UI_STATE_STALE) AND the panel no longer shows the CROSS FAST minimum speed."""
    cross = dict(reference_states())["generator_cross_fast"]
    assert cross["verdict"]["state"] == "CROSS FAST"
    d = tmp_path / "jsapp"
    d.mkdir()
    (d / "package.json").write_text('{"type": "module"}')
    for name in ("model.js", "fields.js", "panel.js", "app.js"):
        shutil.copy(WEB / "js" / name, d / name)
    script = "import { createRequire } from 'module'; const require = createRequire(import.meta.url);\n" + APP_TICK_SCRIPT
    p = subprocess.run([NODE, "--input-type=module", "-e", script, d.as_uri()], input=json.dumps({"state": cross}),
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert out["fresh"]["verdict"] == "CROSS FAST" and "m/s" in out["fresh"]["minSpeed"], out
    assert out["stale"]["verdict"] == "CLOSED" and out["stale"]["override"], out
    assert out["stale"]["minSpeed"] == "—", out


# --------------------------------------------------------------------------------------------- sim-link line (R9-08/09)
PANEL_SCRIPT = r"""
const els = {};
function mk(id) {
  const o = { id, textContent: "", hidden: false, className: "", children: [], style: {}, value: "", options: [],
              replaceChildren(...c) { this.children = c; }, append(...c) { this.children.push(...c); },
              setAttribute() {}, getContext() { return null; } };
  o.tBodies = [{ replaceChildren() {} }];
  return o;
}
globalThis.document = { getElementById: (id) => (els[id] = els[id] || mk(id)), createElement: (t) => mk(t),
                        createTextNode: (t) => ({ textContent: t }) };
const p = await import(process.argv[1] + "/panel.js");
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const client = { hasState: true, wsOpen: true, sinceRxS: 0.1 };
const out = {};
for (const [name, st] of Object.entries(input.states)) {
  const shown = p.renderVerdict(st, client);
  p.renderPanel(st, client, shown);
  const n = els["simlink-line"];
  out[name] = { hidden: n.hidden, text: n.children.map((c) => c.textContent).join(""),
                bad: n.children.filter((c) => c.className === "st-bad").map((c) => c.textContent) };
}
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_simlink_line_shows_disabled_link_and_refused_closures(tmp_path):
    refs = dict(reference_states())
    base = refs["generator_cross_fast"]
    assert base["simlink"]["enabled"] is True and base["simlink"]["blocked"] is True

    def with_sl(**kw):
        s = json.loads(json.dumps(base))
        s["simlink"].update(kw)
        return s

    states = {
        "off": dict(json.loads(json.dumps(base)), simlink={"enabled": False}),
        "blocked": base,
        "refused": with_sl(blocked=False, blocked_reason="", connected=True, queued=0, closures_held=1,
                           not_closed_in_routing=[{"event": "CLOSED", "status": "refused",
                                                   "error": "SNAP_TOO_FAR: 900 m"}]),
        "ok": with_sl(blocked=False, blocked_reason="", connected=True, queued=1, closures_held=1,
                      not_closed_in_routing=[]),
    }
    d = tmp_path / "jspanel"
    d.mkdir()
    (d / "package.json").write_text('{"type": "module"}')
    for name in ("model.js", "fields.js", "panel.js"):
        shutil.copy(WEB / "js" / name, d / name)
    script = "import { createRequire } from 'module'; const require = createRequire(import.meta.url);\n" + PANEL_SCRIPT
    p = subprocess.run([NODE, "--input-type=module", "-e", script, d.as_uri()], input=json.dumps({"states": states}),
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert out["off"]["hidden"] is True
    assert not out["blocked"]["hidden"] and any("Routing link DISABLED" in b and "replay" in b for b in out["blocked"]["bad"])
    assert any("ROAD NOT CLOSED IN ROUTING" in b for b in out["refused"]["bad"])
    assert not any("ROAD NOT CLOSED" in b or "DISABLED" in b for b in out["ok"]["bad"])
    assert "1 not yet confirmed" in out["ok"]["text"] and "connected" in out["ok"]["text"]
