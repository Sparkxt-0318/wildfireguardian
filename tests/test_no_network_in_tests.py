"""The network guard is graded here, not assumed (WFG-139).

``tests/conftest.py`` installs a session-wide block on outbound sockets so that
CHARTER §4b — 「No test may depend on the ... network」 — is enforced by the
machine instead of by eleven laps watching a 25 MB file appear on disk.

A guard nobody grades is the vacuous-binding class this repository keeps
catching (WFG-156), and this guard has already been vacuous once: its first
draft exempted loopback, which looks obviously safe and blocked nothing here,
because the sandbox routes egress through ``HTTPS_PROXY=http://127.0.0.1:38639``.
So the cases below are the ones that actually separate a working guard from a
decorative one, and the loopback-proxy case is asserted directly.

⚠ **What these tests do NOT show.** They show the guard refuses the calls the
standard library funnels connections through (``socket.connect``,
``socket.connect_ex``, ``socket.create_connection``, and therefore ``urllib``,
``http.client`` and ``requests``). They do not show that no code path anywhere
can reach a network: a C extension calling ``connect(2)`` directly, a
subprocess, or a loopback service that forwards traffic without appearing in the
environment's proxy variables would all be invisible here. What covers those is
not a test at all but ``conftest.pytest_sessionfinish``, which fails the run if
``data/raw/`` grew while it was running — the measurement WFG-139 was opened on,
taken automatically instead of by a lap that remembers to look.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from tests.conftest import (
    ALLOW_ENV_VAR,
    NetworkUseInTestError,
    _is_exempt,
    _proxy_endpoints,
)


def test_a_plain_outbound_connect_is_refused() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkUseInTestError):
            sock.connect(("93.184.216.34", 80))
    finally:
        sock.close()


def test_connect_ex_is_refused_too() -> None:
    """``connect_ex`` returns an errno instead of raising, so it needs its own
    guard: a caller that only checks the return value would otherwise open a
    real connection while the suite believed it could not."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkUseInTestError):
            sock.connect_ex(("93.184.216.34", 80))
    finally:
        sock.close()


def test_create_connection_is_refused() -> None:
    """The call ``urllib`` and ``http.client`` actually reach the network by."""
    with pytest.raises(NetworkUseInTestError):
        socket.create_connection(("elevation-tiles-prod.s3.amazonaws.com", 443))


def test_a_loopback_proxy_is_refused_even_though_it_is_loopback() -> None:
    """The case the first draft of the guard got wrong.

    Egress through a proxy listening on 127.0.0.1 is still egress. This asserts
    the rule on a synthetic proxy set rather than on the ambient environment, so
    it is the same test on a machine that has no proxy configured.
    """
    proxies = frozenset({("127.0.0.1", 38639)})
    assert _is_exempt(("127.0.0.1", 9999), proxies) is True
    assert _is_exempt(("127.0.0.1", 38639), proxies) is False
    assert _is_exempt(("52.216.0.1", 443), proxies) is False
    assert _is_exempt("/run/some.sock", proxies) is True


def test_the_proxy_reader_reads_both_spellings(monkeypatch) -> None:
    """``https_proxy`` and ``HTTPS_PROXY`` are both real; both must be seen."""
    for name in ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:1111")
    monkeypatch.setenv("HTTP_PROXY", "10.0.0.9:2222")  # no scheme, still a proxy
    assert _proxy_endpoints() == frozenset({("127.0.0.1", 1111), ("10.0.0.9", 2222)})


def test_binding_and_listening_are_left_alone() -> None:
    """``tests/test_api.py`` binds a loopback port on purpose; a bind is not a
    connect, and blocking it would break a test that never touches a network."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        assert sock.getsockname()[1] > 0
    finally:
        sock.close()


def test_a_genuine_loopback_connection_still_works() -> None:
    """A browser this repository launched is talked to over a loopback port
    (``tests/test_finals_acts.py`` drives Chromium's CDP endpoint), so the guard
    must not refuse loopback wholesale."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        client.settimeout(5.0)
        client.connect(server.getsockname())
        conn, _ = server.accept()
        conn.close()
    finally:
        client.close()
        server.close()


def test_the_srtm_downloader_is_stopped_before_it_opens_a_url() -> None:
    """The WFG-139 predicate itself, on the function the row named.

    ``_download_srtm_tile`` catches ``(URLError, OSError, TimeoutError)`` and
    re-raises ``FileNotFoundError``, which callers read as 「no tile」. The guard
    raises a ``RuntimeError`` subclass for exactly that reason, so it propagates
    instead of being converted into a silent fallback.
    """
    from wildfireguardian.data_io import raster

    with pytest.raises(NetworkUseInTestError):
        raster._download_srtm_tile(0, 0, timeout_s=1.0)


def test_the_whole_run_measurement_is_a_hook_and_not_a_test(tmp_path) -> None:
    """The 「did this run download anything」 check lives in ``pytest_sessionfinish``,
    and it has to.

    A *test* cannot make that measurement. pytest runs files in collection order
    and this file sorts before ``test_raster_ingestion.py`` and
    ``test_spread_warmup.py``, so a test here reads the disk BEFORE the two tests
    that used to download have run: it would have passed for the wrong reason on
    the exact tree that motivated it. The first draft of this file did that. What
    is asserted here is the helper the hook uses, on a directory this test builds,
    plus the fact that the hook is wired up at all.
    """
    from tests import conftest as guard

    assert hasattr(guard, "pytest_sessionfinish")
    assert guard._tree_bytes(tmp_path / "absent") == 0
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.bin").write_bytes(b"x" * 10)
    (tmp_path / "b.bin").write_bytes(b"y" * 7)
    assert guard._tree_bytes(tmp_path) == 17


def _files_naming(root: Path, var: str) -> list[str]:
    """Repo-relative paths of runnable files that mention ``var`` at all.

    The NAME, not one spelling of an assignment. The first version of this
    helper searched for the literal ``WFG_TESTS_ALLOW_NETWORK=1``, which is the
    **shell** spelling only: a GitHub Actions workflow writes
    ``WFG_TESTS_ALLOW_NETWORK: 1`` and Python writes
    ``os.environ["WFG_TESTS_ALLOW_NETWORK"] = "1"``. It could not fire on two of
    the three file classes it scanned, inside the very file written to prove
    this guard is not vacuous. Found by this lap's independent reviewer.
    """
    hits: list[str] = []
    patterns = ("*.yml", "*.yaml", "*.sh", "*.py", "*.toml", "*.cfg", "*.ini")
    seen: set[Path] = set()
    for sub in (".github", "scripts", "Makefile"):
        base = root / sub
        if base.is_file():
            seen.add(base)
            continue
        for pat in patterns:
            seen.update(p for p in base.rglob(pat) if p.is_file())
    for path in sorted(seen):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if var in text:
            hits.append(str(path.relative_to(root)))
    return hits


def test_the_setter_detector_sees_every_spelling(tmp_path) -> None:
    """Grade the detector before trusting it, on a planted tree.

    Three spellings, three file kinds, and a decoy that names a different
    variable — because a detector that returns everything is as useless as one
    that returns nothing.
    """
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "env:\n  WFG_TESTS_ALLOW_NETWORK: 1\n", encoding="utf-8")
    (tmp_path / "scripts" / "warm.sh").write_text(
        "export WFG_TESTS_ALLOW_NETWORK=1\n", encoding="utf-8")
    (tmp_path / "scripts" / "warm.py").write_text(
        'os.environ["WFG_TESTS_ALLOW_NETWORK"] = "1"\n', encoding="utf-8")
    (tmp_path / "scripts" / "innocent.py").write_text(
        'os.environ["SOMETHING_ELSE"] = "1"\n', encoding="utf-8")
    (tmp_path / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")

    found = _files_naming(tmp_path, ALLOW_ENV_VAR)
    assert found == [
        ".github/workflows/ci.yml",
        "scripts/warm.py",
        "scripts/warm.sh",
    ], found


def test_the_escape_hatch_is_named_and_unused() -> None:
    """The env var exists for a human warming a cache by hand. If a gate or a
    workflow ever sets it, the guard is off for that run and nobody would
    notice, so the repository is asserted not to name it anywhere runnable."""
    root = Path(__file__).resolve().parents[1]
    setters = _files_naming(root, ALLOW_ENV_VAR)
    assert setters == [], (
        f"{ALLOW_ENV_VAR} is named by {setters}, which can turn the network guard "
        "off for that run. Remove it, or say in writing why that run may use a "
        "network."
    )
