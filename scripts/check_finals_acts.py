#!/usr/bin/env python3
"""Advance the four acts of `web/finals.html` in a real browser and screenshot each.

What readiness line R1 asks, and what was missing
-------------------------------------------------
R1: 「`web/finals.html` opens from `file://` with Wi-Fi off, **all four acts
advance**, every on-screen number maps to a `docs/NUMBERS.json` key」.  The mapping
clause closed at `60c07c8` (WFG-110).  The **advance** clause had never been
exercised by anything in this repository: its only evidence was one hand-run
recorded in `docs/auto/finals/BOOTH_SETUP.md` §3 on 2026-09-05, on a build the
screen has been rebuilt past many times.

⚠ **The four acts are not the four view tabs.**  Critic #36 measured the four
*views* (`view-live`, `view-evidence`, `view-reliability`, `view-system`; the tabs
라이브 · 시스템 · 근거 · 신뢰성) and reported that two of them hold no Korean text
until a switch.  That is true and it is a different mechanism.  The **acts** are the
guided demo's 막 — `1막 · 발견`, `2막 · 시간과 도로망`, `3막 · 경로 비교`,
`4막 · 판단` — the sequence `docs/auto/DEMO_SCRIPT_5MIN.md` walks a judge through,
driven by `#gNext` inside the `#guide` dialog.  This script drives the acts.

What it does
------------
1. Copies `web/` **whole** into a temp directory and loads it from there, so a file
   the screen needs but the bundle forgets shows up as a failure here rather than
   at the booth.
2. Launches the sandbox's Chromium headless with remote debugging, and drives it
   over the DevTools protocol (`scripts/cdp_min.py`, stdlib only — no Playwright in
   this sandbox and no wheel may be downloaded; CHARTER §4b).
3. Presses `#introGo` with a real mouse event, which is the judge's own path into
   the guided demo, then presses `#gNext` with real mouse events until act 4.
4. After every press, reads the act label, the progress dots and the caption, and
   **asserts the act actually changed** — see `_assert_advanced`, which is the
   whole point of the script.
5. Screenshots each act, records every request URL and every console error.

What it does NOT show
---------------------
It does not show that the screen is *correct*, only that four acts advance without
a console error and without reaching off `file://`.  It renders at one viewport on
one Chromium build on Linux; the booth laptop is not this machine.  It presses
buttons, so it says nothing about the keyboard path (`g`, arrow keys) that
`BOOTH_SETUP.md` also documents.  `docs/finals_acts_smoke.md` carries the caveats.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_min import CDP, CDPError, page_target  # noqa: E402


class NoBrowser(Exception):
    """Chromium is absent.  A skip, never a download (CHARTER §4b)."""


class BrowserLaunchError(CDPError):
    """Chromium was found and started, and never opened its debugging port.

    A machine fact about the runner, not a finding about `web/finals.html`, and
    the only failure this driver lets a caller treat as one.  It is a TYPE so
    that callers discriminate by `isinstance` rather than by matching words in a
    message: `tests/test_finals_acts.py` used to skip on the substring 「no page
    target on port」, which would have swallowed that message from any source.
    """

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "web"

#: Where the sandbox and the CI image keep Chromium.  Checked in order; the first
#: that exists wins.  Nothing is downloaded: absent means skip, never fetch.
CHROME_CANDIDATES = (
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
)

#: The four acts as `web/finals.html` labels them in Korean, in order.  Taken from
#: the screen's own `T('guided').acts`, which `DEMO_SCRIPT_5MIN.md` §66+ recites.
ACT_LABELS = ["1막 · 발견", "2막 · 시간과 도로망", "3막 · 경로 비교", "4막 · 판단"]

#: `GUIDED.next()` splits act 3 into two steps (STATIC VIEW, then TIME-AWARE VIEW),
#: so reaching act 4 takes more presses than there are acts.  A driver that assumed
#: one press per act would stop on the static half of act 3 and call it act 4.
MAX_PRESSES = 8


def find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if Path(c).exists() and os.access(c, os.X_OK):
            return c
    return shutil.which("chromium") or shutil.which("google-chrome")


#: How long to wait for Chromium to publish its debugging port, and how many
#: times to start it before calling the machine broken.  Two attempts, because a
#: launch that fails for a transient reason is the case WFG-196 asked to cover
#: and a second one costs a few seconds; a browser that is genuinely gone fails
#: both and the job goes red, which is the half that must not be softened.
LAUNCH_TIMEOUT = 30.0
LAUNCH_ATTEMPTS = 2


def _launch(chrome: str, profile: Path, stderr_path: Path) -> tuple[subprocess.Popen, int]:
    """Start Chromium and return it with the port it is actually listening on.

    ⚠ The port is **not** chosen here, and that is the whole point of this
    function.  Until 2026-09-08 it was: `_free_port()` bound an ephemeral port,
    closed it, and passed the number to Chromium, which bound it again some
    hundreds of milliseconds later.  Anything else on the machine could take it
    in that window, and on a GitHub runner something does.  Chromium does not
    fail when it cannot bind: it logs 「bind() failed: Address already in use
    (98)」, keeps running with no DevTools endpoint at all, and the driver then
    polls a port nobody is listening on until it times out.  That is exactly the
    shape `auto-gates` went red in twice -- 「no page target on port 51449 within
    30.0s (last: <urlopen error [Errno 111] Connection refused>)」 at `b7c1837`
    (run 255) and the same on port 58173 at `7eeccab` (run 260) -- and the
    runner's own cleanup line 「Terminate orphan process: pid (2032) (chrome)」
    is the tell that the browser was alive the whole time.  Reproduced
    deliberately in the sandbox by holding the port open across the launch.

    So Chromium is asked for port 0 and picks its own, which it cannot race with
    anyone, and it writes the result to `DevToolsActivePort` in the profile
    directory.  Reading that file is how Playwright and puppeteer do it too.
    """
    stderr_handle = stderr_path.open("wb")
    proc = subprocess.Popen(
        [
            chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", "--window-size=1440,900",
            "--force-device-scale-factor=1", "--disable-lcd-text",
            # Port 0 means 「choose one and tell me which」; see the note above.
            "--remote-debugging-port=0", f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check",
            # Nothing may leave the machine.  If the screen ever grows a remote
            # asset, the request is recorded below and the gate fails on it.
            "--disable-background-networking", "--disable-component-update",
            "--disable-default-apps", "--disable-sync", "--metrics-recording-only",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=stderr_handle,
    )
    # ⚠ Chromium's stderr is kept rather than sent to DEVNULL, which is where it
    # went while two laps guessed at this failure from the outside.  The one line
    # that names the cause is in there.
    active = profile / "DevToolsActivePort"
    deadline = time.time() + LAUNCH_TIMEOUT
    try:
        while time.time() < deadline:
            if active.exists():
                first = active.read_text(errors="replace").splitlines()[:1]
                # The file is written in one go, but it is read while another
                # process writes it, so a half-line is possible and is not a port.
                if first and first[0].strip().isdigit():
                    return proc, int(first[0].strip())
            if proc.poll() is not None:
                break  # it died; no amount of waiting will produce a port
            time.sleep(0.1)
    finally:
        stderr_handle.close()
    with contextlib.suppress(Exception):
        proc.terminate()
        proc.wait(timeout=10)
    why = "exited with %s" % proc.poll() if proc.poll() is not None else \
        f"stayed up for {LAUNCH_TIMEOUT}s without writing {active.name}"
    tail = stderr_path.read_text(errors="replace").strip().splitlines()[-8:]
    raise BrowserLaunchError(
        f"Chromium ({chrome}) {why}. Its last stderr lines:\n  "
        + ("\n  ".join(tail) if tail else "(it printed nothing)")
    )


#: The state the screen exposes about the guided demo, read in one round trip.
#: `dots` is how many progress pips are lit, which the screen sets to `act + 1`.
#: ⚠ Reading it as well as the label is a REDUNDANCY, not an independent witness:
#: `enter()` in web/finals.html sets the label, the caption and the dots from the
#: same `act` argument in one synchronous block, so a state where the label moved
#: and the dots did not cannot arise from the screen as it stands today. It is here
#: to catch the version of this screen where they DO come apart. Corrected after
#: this lap's reviewer read `enter()`; the first draft called it an independent
#: witness, which was an overstatement about code nobody had opened.
_STATE_JS = """
(() => {
  const q = (id) => document.getElementById(id);
  const guide = q('guide');
  return JSON.stringify({
    guideVisible: !!guide && !guide.hidden,
    act: q('gact') ? q('gact').textContent.trim() : null,
    title: q('gtitle') ? q('gtitle').textContent.trim() : '',
    body: q('gbody') ? q('gbody').textContent.trim() : '',
    dots: q('gdots') ? q('gdots').querySelectorAll('i.on').length : -1,
    view: (() => { const v = document.querySelector('section.view.on');
                   return v ? v.id : null; })(),
    introHidden: !!(q('intro') === null || (q('intro') && q('intro').hidden)),
  });
})()
"""


def _wait_until(cdp: CDP, expression: str, what: str, timeout: float = 25.0) -> None:
    """Poll a JS predicate instead of sleeping a guessed number of seconds.

    ⚠ This is here because of CI, not because of this sandbox.  A fixed
    `time.sleep(3)` after `Page.navigate` is enough on the machine the author
    happens to run it on and is a coin flip on a slower shared runner: the screen
    parses a 3.4 MB inline payload and builds an SVG before the intro is pressable.
    A gate that turns `auto-gates` red at random is worse than no gate, so the
    driver waits for the condition it actually needs.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cdp.evaluate(expression) is True:
                return
        except CDPError:
            pass  # the document can be mid-navigation; try again
        time.sleep(0.2)
    raise AssertionError(f"timed out after {timeout:.0f}s waiting for {what}")


def _click(cdp: CDP, selector: str) -> None:
    """A real mouse press/release at the element's centre, not `.click()`.

    `element.click()` runs the handler even when the button is covered, disabled by
    CSS or scrolled out of the dialog.  A judge cannot press a covered button, so
    neither does this driver: the coordinates come from the live bounding box and
    the event goes in through `Input`, where the browser does the hit testing.
    """
    box = cdp.evaluate(
        "(() => { const e = document.querySelector(" + json.dumps(selector) + ");"
        " if (!e) return null; const r = e.getBoundingClientRect();"
        " if (r.width === 0 || r.height === 0) return null;"
        " return JSON.stringify({x: r.left + r.width / 2, y: r.top + r.height / 2}); })()"
    )
    if not box:
        raise CDPError(f"{selector} is absent or has no rendered box; cannot press it")
    pos = json.loads(box)
    for kind in ("mousePressed", "mouseReleased"):
        cdp.call(
            "Input.dispatchMouseEvent", type=kind, x=pos["x"], y=pos["y"],
            button="left", clickCount=1,
        )
    time.sleep(0.45)


#: Open the 시스템 구조 tab, toggle the language twice, and count the blocks
#: renderSystem() appends. One of each is correct; more than one is the append
#: bug. Returns a JSON object so the report records the counts either way.
_SYS_DUP_JS = """(() => {
  const tab = [...document.querySelectorAll('button, a')]
    .find(el => (el.textContent || '').includes('시스템'));
  if (tab) tab.click();
  const lang = document.getElementById('btnLang');
  if (lang) { lang.click(); lang.click(); }
  if (tab) tab.click();
  const n = (id) => document.querySelectorAll('#' + id).length;
  return JSON.stringify({syssrc: n('syssrc'), sysnote: n('sysnote'),
                         syscreative: n('syscreative')});
})()"""


def _state(cdp: CDP) -> dict:
    return json.loads(cdp.evaluate(_STATE_JS))


def _assert_advanced(previous: dict, current: dict, expected_label: str) -> None:
    """The assertion this row exists for.

    A driver that presses a button and writes a PNG proves only that the browser
    did not crash: if the handler silently failed, the dialog would still be on
    screen, the screenshot would still be written and the gate would still pass.
    So every act must differ from the one before it in the label the judge reads
    AND carry the caption text and the lit-dot count the screen owes it.
    """
    problems = []
    if not current["guideVisible"]:
        problems.append("the guided dialog is not visible")
    if current["act"] != expected_label:
        problems.append(f"act label is {current['act']!r}, expected {expected_label!r}")
    if current["act"] == previous.get("act"):
        problems.append(f"act label did not change from {previous.get('act')!r}")
    if current["dots"] != ACT_LABELS.index(expected_label) + 1:
        problems.append(
            f"{current['dots']} progress dots lit, expected "
            f"{ACT_LABELS.index(expected_label) + 1}"
        )
    if not current["title"]:
        problems.append("the act caption title is empty")
    if not current["body"]:
        problems.append("the act caption body is empty")
    if current["view"] != "view-live":
        problems.append(f"the guided demo left the live view (showing {current['view']})")
    if problems:
        raise AssertionError(
            f"act 「{expected_label}」 did not advance:\n  " + "\n  ".join(problems)
        )


def tracked_demo_media() -> frozenset[str]:
    """Basenames of the files actually committed under `web/demo-media/`."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "web/demo-media"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    return frozenset(Path(p).name for p in out.split("\0") if p)


def _is_optional_media(url: str, tracked: frozenset[str] | None = None) -> bool:
    """True only for an **unfilled** booth media slot.

    `web/demo-media/README.md` declares these slots optional — 「전부 없어도 화면은
    완전하게 동작한다(지형 정지 화면 + 무음 대체)」 — and the author drops the real
    files onto the booth laptop, so a clean clone and CI never have them.

    ⚠ **The predicate is the git INDEX, not a list of file extensions.**  The first
    version of this function tolerated a hardcoded extension list and its comment
    claimed those were 「the extensions .gitignore excludes」.  That was false:
    `.gitignore` excludes only `*.mp4 *.mov *.avi`, so `.mp3`, `.wav` and the rest
    were tolerated on a premise that did not hold, and `web/finals.html` references
    five committable `.wav` UI-sound slots that the tolerance would have silently
    covered.  Asking the index instead says exactly the true thing: **a file
    committed under `demo-media/` must load, and one that was never committed is a
    slot nobody has filled.**  Found by this lap's independent reviewer.

    Nothing outside `demo-media/` is ever optional, so a missing font, stylesheet or
    script fails wherever it lives — a blanket "ignore missing files" would have made
    this gate agree with a booth laptop that had lost its fonts.
    """
    if "/demo-media/" not in url:
        return False
    if tracked is None:
        tracked = tracked_demo_media()
    name = url.split("?", 1)[0].split("#", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return bool(name) and name not in tracked


def _console_errors(cdp: CDP) -> tuple[list[str], list[str]]:
    """(errors that fail the gate, optional-media misses recorded but tolerated)."""
    fatal: list[str] = []
    tolerated: list[str] = []
    tracked = tracked_demo_media()
    for ev in cdp.events:
        m, p = ev.get("method"), ev.get("params", {})
        if m == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {})
            fatal.append(
                f"uncaught: {d.get('text')} "
                f"{d.get('exception', {}).get('description', '')}".strip())
        elif m == "Runtime.consoleAPICalled" and p.get("type") == "error":
            fatal.append("console.error: " + " ".join(
                str(a.get("value", a.get("description", ""))) for a in p.get("args", [])))
        elif m == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
            e = p["entry"]
            line = f"log[{e.get('source')}]: {e.get('text')} {e.get('url', '')}".strip()
            (tolerated if _is_optional_media(e.get("url", ""), tracked)
             else fatal).append(line)
    return fatal, tolerated


def _requested_urls(cdp: CDP) -> list[str]:
    return [
        ev["params"]["request"]["url"]
        for ev in cdp.events
        if ev.get("method") == "Network.requestWillBeSent"
    ]


def run(out_dir: Path, keep: bool = False) -> dict:
    chrome = find_chrome()
    if chrome is None:
        raise NoBrowser(
            "no Chromium on this machine; this gate never downloads one "
            f"(looked in: {', '.join(CHROME_CANDIDATES)})"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix="wfg-finals-"))
    #: One profile per attempt: a relaunch must not read the previous attempt's
    #: `DevToolsActivePort` and take a dead browser's port for its own.
    profiles: list[Path] = []
    try:
        # The WHOLE of web/, so a missing sibling asset fails here, not at the booth.
        shutil.copytree(WEB, staged / "web")
        page = (staged / "web" / "finals.html").resolve()
        launch_failure: BrowserLaunchError | None = None
        proc = port = None
        for attempt in range(1, LAUNCH_ATTEMPTS + 1):
            profile = Path(tempfile.mkdtemp(prefix="wfg-profile-"))
            profiles.append(profile)
            try:
                proc, port = _launch(chrome, profile, profile / "chrome-stderr.log")
                break
            except BrowserLaunchError as exc:
                launch_failure = exc
                print(f"    (browser launch attempt {attempt} of "
                      f"{LAUNCH_ATTEMPTS} failed: {exc})", file=sys.stderr)
        if proc is None or port is None:
            assert launch_failure is not None
            raise launch_failure
        try:
            cdp = CDP(page_target(port))
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Log.enable")
            cdp.call("Network.enable")
            cdp.call("Page.navigate", url=page.as_uri())
            # Ready means the intro's primary button is laid out and labelled — the
            # screen fills its text from T() after the payload parses, so a button
            # with an empty label is a page that is not finished.
            _wait_until(
                cdp,
                "(() => { const e = document.getElementById('introGo');"
                " return !!e && e.getBoundingClientRect().width > 0"
                " && e.textContent.trim().length > 0; })()",
                "web/finals.html to finish building the intro",
            )
            cdp.drain()

            acts = []
            # The judge's own way in: the intro's primary button starts the demo.
            _click(cdp, "#introGo")
            _wait_until(
                cdp,
                "(() => { const g = document.getElementById('guide');"
                " const a = document.getElementById('gact');"
                " return !!g && !g.hidden && !!a && a.textContent.trim().length > 0; })()",
                "the guided demo to open on its first act",
            )
            cdp.drain()
            state = _state(cdp)
            previous: dict = {}
            presses = 0
            for expected in ACT_LABELS:
                while state["act"] != expected and presses < MAX_PRESSES:
                    before = state
                    _click(cdp, "#gNext")
                    # ⚠ Wait for the caption to CHANGE, not for the label to change:
                    # act 3 advances through two steps under the same label
                    # (STATIC VIEW -> TIME-AWARE VIEW) and only the body moves.
                    # Waiting on the label alone would hang there for the timeout.
                    _wait_until(
                        cdp,
                        "(() => { const q = (i) => (document.getElementById(i) || {})"
                        ".textContent || '';"
                        " const was = " + json.dumps([before["act"] or "", before["body"]])
                        + "; return q('gact').trim() !== was[0]"
                        " || q('gbody').trim() !== was[1]; })()",
                        f"the caption to change after pressing 다음 (at {before['act']!r})",
                    )
                    cdp.drain()
                    state = _state(cdp)
                    presses += 1
                _assert_advanced(previous, state, expected)
                shot = cdp.call(
                    "Page.captureScreenshot", format="png", captureBeyondViewport=False
                )
                name = f"act{ACT_LABELS.index(expected) + 1}.png"
                (out_dir / name).write_bytes(base64.b64decode(shot["data"]))
                acts.append({
                    "act": expected, "screenshot": name,
                    "dots": state["dots"], "title": state["title"],
                    "presses_so_far": presses,
                })
                previous = state

            # ⚠ The 시스템 구조 tab, opened and language-toggled, WFG-194.
            # renderSystem() appends its source strip, its operator note and its
            # 창의성 block into the page, and setLang() sets sysBuilt = false and
            # calls it again - so before this lap one toggle left two of each and
            # two toggles left three, with duplicate element ids. Nobody had ever
            # driven it: the acts loop above never leaves the 상황 tab. The booth
            # script now tells the student to open this tab when a judge asks
            # what is new, so the count is asserted rather than assumed.
            sys_counts = json.loads(cdp.evaluate(_SYS_DUP_JS))
            duplicated = {k: v for k, v in sys_counts.items() if v != 1}

            cdp.drain()
            errors, optional_misses = _console_errors(cdp)
            urls = _requested_urls(cdp)
            # ⚠ The scheme check must run on the RAW urls.  Normalising first strips
            # the `file://` prefix and makes every request look off-site — which is
            # exactly what this gate did on its first run, and it failed loudly
            # rather than passing, which is the behaviour worth keeping.
            offsite = [u for u in urls
                       if not u.startswith(("file://", "data:", "blob:", "about:"))]

            # The staged copy lives under a per-run temp directory.  Leaving that
            # path in the report makes two identical runs look different and puts a
            # machine-specific string into a committed artifact, so it is folded
            # back to the repository-relative name it stands for.
            staged_uri = (staged / "web").as_uri()

            def _rel(s: str) -> str:
                return s.replace(staged_uri, "web").replace(str(staged / "web"), "web")

            errors = [_rel(e) for e in errors]
            optional_misses = [_rel(e) for e in optional_misses]
            urls = [_rel(u) for u in urls]
            version = subprocess.run(
                [chrome, "--version"], capture_output=True, text=True, check=False
            ).stdout.strip()
            report = {
                "browser": version, "browser_path": chrome,
                "page": "web/finals.html (copied whole into a temp dir)",
                "acts": acts, "presses_total": presses,
                "console_errors": errors,
                "optional_media_missing": optional_misses,
                "requests_total": len(urls), "offsite_requests": offsite,
                "system_tab_elements_after_two_language_toggles": sys_counts,
            }
            if errors:
                raise AssertionError("console errors while advancing the acts:\n  "
                                     + "\n  ".join(errors))
            if offsite:
                raise AssertionError("the screen requested something off file://:\n  "
                                     + "\n  ".join(offsite))
            if duplicated:
                raise AssertionError(
                    "the 시스템 구조 tab stacks its own blocks when the language is "
                    "toggled, so a judge sees each one more than once and the page "
                    "carries duplicate element ids: "
                    + ", ".join(f"{k} x{v}" for k, v in sorted(duplicated.items()))
                    + ". renderSystem() appends into #view-system .page; remove the "
                      "previous nodes by id before rebuilding.")
            return report
        finally:
            with contextlib.suppress(Exception):
                proc.terminate()
                proc.wait(timeout=10)
    finally:
        if not keep:
            shutil.rmtree(staged, ignore_errors=True)
        for used in profiles:
            shutil.rmtree(used, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO / ".auto" / "finals_acts"),
                    help="where the four screenshots and report.json are written")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--keep", action="store_true", help="keep the staged copy of web/")
    args = ap.parse_args()
    out = Path(args.out)
    try:
        report = run(out, keep=args.keep)
    except NoBrowser as exc:
        print(f"=== check_finals_acts: SKIPPED === {exc}")
        return 0
    except (AssertionError, CDPError) as exc:
        print(f"=== check_finals_acts: FAILED ===\n{exc}")
        return 1
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"=== check_finals_acts: PASSED === {report['browser']}")
        for a in report["acts"]:
            print(f"    {a['act']:<20s} {a['dots']} dots  -> {a['screenshot']}")
        print(f"    {report['requests_total']} requests, none off file://, "
              f"no console error")
        for miss in report["optional_media_missing"]:
            print(f"    (optional booth media absent, by design: {miss})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
