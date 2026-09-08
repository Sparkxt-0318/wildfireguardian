"""Test-suite-wide guards.

WFG-139. CHARTER §4b says, in these words: 「No test may depend on the local
clock, the timezone, the network, or files outside the repository.」 Eleven
consecutive laps measured the suite breaking the network half of that rule, and
every one of them measured it the same way — by watching a 25 MB file appear in
``data/raw/dem/srtm/`` during a 200-to-350-second ``pytest-full`` stage. That
proves *a* download happened; it never proved *which line* did it, and it can
only be seen on a cold machine, so a warm re-run always looks innocent.

This file replaces that inference with a mechanism. Every test **body** runs
with outbound TCP connections blocked, so a test that reaches the network
**fails, loudly, naming this rule**, on any machine, warm or cold, in CI or in a
sandbox. The evidence that only one test was reaching the network is then
produced by the machine rather than by a grep somebody wrote and graded
themselves. It said two, not one.

What is blocked: ``connect``/``connect_ex`` on a socket object, and
``socket.create_connection``, to any address that **is not loopback**, and to
any address that **is a configured HTTP proxy** even when that proxy is on
loopback. What is NOT blocked: a genuinely local loopback connection, binding
and listening (``tests/test_api.py`` binds a 127.0.0.1 port to prove uvicorn's
preload ordering, and a bind is not a connect), AF_UNIX sockets, and anything in
a process this suite does not own.

⚠ **The proxy clause is not defensive programming; the first draft of this file
lacked it and blocked nothing.** That draft allowed loopback, which reads as
obviously safe and is not: the sandbox this loop runs in sets
``HTTPS_PROXY=http://127.0.0.1:38639``, so the S3 download this rule exists to
stop connects to **127.0.0.1** and went straight through. Measured rather than
argued — with the loopback allowance in place,
``test_model_config_ignition_radius_increases_initial_burn`` passed and
``data/raw/`` still grew from 201,187 B to 34,609,457 B. A guard that cannot see
egress through a local proxy is the vacuous-binding class (WFG-156) inside the
very mechanism written to end a measurement problem. A proxy is egress by
definition, so the endpoints named in ``*_proxy``/``*_PROXY`` are refused
wherever they sit.

⚠ **What that leaves open, enumerated rather than implied.** Named by this
lap's independent reviewer, not by the lap that wrote the guard:

* **import and collection time.** This is a session *fixture*, and fixtures are
  set up after collection, so a module-level network call in a test file runs
  unguarded. That is why the paragraph above says test *body*.
* **UDP.** ``sendto``/``sendmsg`` are not patched.
* **Name resolution.** ``getaddrinfo`` is not patched, so a test can still
  depend on DNS — half of what CHARTER §4b forbids.
* **A loopback forwarder nobody declared.** A service that proxies off the
  machine without appearing in a ``*_proxy`` variable is invisible here.
* **``pytest`` run on a path outside ``tests/``**, which loads no ``conftest``
  and therefore no guard.
* A C extension calling ``connect(2)`` directly, and any subprocess.

``pytest_sessionfinish`` below covers what those leave behind in ``data/raw/``,
and nothing else. The two loopback connections this suite actually makes were
separated by the rule on evidence rather than by assumption: the Chromium CDP
port in ``tests/test_finals_acts.py`` is an ephemeral port of a browser this
repository launched, and the SRTM fetch went to the port in ``HTTPS_PROXY``.

**There is deliberately no marker to opt a single test out.** CHARTER §4b has no
exception for a test that is only a little networked, and a marker is how that
exception gets written. The one escape is the environment variable
``WFG_TESTS_ALLOW_NETWORK=1``, which exists for a developer who wants to warm a
cache on purpose and which no gate and no CI job sets. Warming the SRTM cache is
a script's job, not a test's: see ``docs/clean_clone_gates.md``.

The guard is graded by ``tests/test_no_network_in_tests.py``: it is asserted to
block a plain ``connect``, to block ``socket.create_connection``, to block a
connect to a **loopback proxy** (the case the first draft got wrong), to leave a
plain loopback connect and a bind alone, and to stop ``_download_srtm_tile``
before it opens a URL.
"""

from __future__ import annotations

import os
import socket
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

#: Set to 1 to lift the block for a whole run. No gate and no workflow sets it.
ALLOW_ENV_VAR = "WFG_TESTS_ALLOW_NETWORK"


class NetworkUseInTestError(RuntimeError):
    """Raised when a test tries to open a network connection.

    Deliberately a ``RuntimeError`` and **not** an ``OSError``: the SRTM tile
    downloader catches ``(urllib.error.URLError, OSError, TimeoutError)`` and
    re-raises ``FileNotFoundError``, which several callers treat as 「no tile,
    fall back」. An ``OSError`` here would therefore be swallowed and the test
    would pass while silently changing what it measured. This one propagates.
    """


_LOOPBACK_HOSTS = frozenset({"::1", "localhost", ""})


def _proxy_endpoints() -> frozenset[tuple[str, int]]:
    """``(host, port)`` pairs of every HTTP proxy the environment names.

    Read once when the guard installs itself. A proxy carries traffic off the
    machine whatever address it listens on, so these are refused even on
    loopback; see the module docstring for the measurement behind that.
    """
    found: set[tuple[str, int]] = set()
    for var in ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy"):
        for name in (var, var.upper()):
            raw = os.environ.get(name)
            if not raw:
                continue
            parsed = urllib.parse.urlparse(
                raw if "://" in raw else "http://" + raw)
            if parsed.hostname and parsed.port:
                port = int(parsed.port)
                found.add((parsed.hostname, port))
                # A proxy spelled `localhost` is dialled as 127.0.0.1 (or ::1)
                # by the time it reaches connect(), and this guard compares the
                # tuple literally. Without these two the same proxy is exempt
                # under one spelling and refused under the other.
                if parsed.hostname == "localhost":
                    found.add(("127.0.0.1", port))
                    found.add(("::1", port))
    return frozenset(found)


def _is_exempt(address: Any, proxies: frozenset[tuple[str, int]]) -> bool:
    """True for addresses this guard leaves alone.

    Non-tuple addresses (an AF_UNIX path, ``str`` or ``bytes``) cannot carry
    traffic off the machine and are exempt. An ``(host, port)`` pair is exempt
    only when the host is loopback AND the pair is not a configured proxy.
    """
    if not (isinstance(address, tuple) and address):
        return True
    host = address[0]
    if not isinstance(host, str):
        return False
    port = address[1] if len(address) > 1 else None
    if isinstance(port, int) and (host, port) in proxies:
        return False
    return host in _LOOPBACK_HOSTS or host.startswith("127.")


def _refuse(where: str, address: Any) -> NetworkUseInTestError:
    return NetworkUseInTestError(
        f"a test tried to open a network connection via {where} to {address!r}. "
        "CHARTER §4b: no test may depend on the network. This is WFG-139 — the "
        "suite used to download a 25 MB SRTM tile here, which made every cold "
        "run differ from every warm one and turned a network outage into a red "
        "gate. Use a committed snapshot, a synthetic source, or a skipif on the "
        "cached input. To warm a cache deliberately, run the acquisition script "
        f"outside pytest, or set {ALLOW_ENV_VAR}=1 for the whole run."
    )


@pytest.fixture(autouse=True, scope="session")
def _no_outbound_network() -> Any:
    """Block outbound socket connections for the whole session."""
    if os.environ.get(ALLOW_ENV_VAR) == "1":
        yield
        return

    proxies = _proxy_endpoints()
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if not _is_exempt(address, proxies):
            raise _refuse("socket.connect", address)
        return real_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any) -> Any:
        if not _is_exempt(address, proxies):
            raise _refuse("socket.connect_ex", address)
        return real_connect_ex(self, address)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        if not _is_exempt(address, proxies):
            raise _refuse("socket.create_connection", address)
        return real_create_connection(address, *args, **kwargs)

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = real_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = real_connect_ex  # type: ignore[method-assign]
        socket.create_connection = real_create_connection  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# The whole-run measurement, so the guard's coverage claim is not vacuous
# ---------------------------------------------------------------------------
#
# The guard above sees the calls the standard library funnels connections
# through. It cannot see a C extension calling connect(2), a subprocess, or a
# loopback service that forwards traffic without appearing in the proxy
# variables. What DOES see all of those is the thing eleven laps were already
# looking at: whether `data/raw/` grew across the run.
#
# A test asserting that cannot do this job, and a first draft of
# tests/test_no_network_in_tests.py tried: pytest runs files in collection
# order, `test_no_network_in_tests.py` sorts before `test_raster_ingestion.py`
# and `test_spread_warmup.py`, so such a test observes the disk BEFORE the tests
# that used to download had run. It would have passed for the wrong reason on
# the exact tree that motivated it. A session hook runs after everything.

_RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def _tree_bytes(root: Path) -> int:
    """Total size of the files under ``root``; 0 if it does not exist."""
    if not root.exists():
        return 0
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


def pytest_configure(config: pytest.Config) -> None:
    config.stash_raw_bytes_at_start = _tree_bytes(_RAW_DIR)  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the run if ``data/raw/`` grew while the tests were running.

    WFG-139's own measurement, taken automatically at the end of every run
    instead of by a lap that remembers to look. It also answers WFG-172's
    「did this run download anything」 for the report, without a network call.
    """
    before = getattr(session.config, "stash_raw_bytes_at_start", None)
    if before is None:
        return
    after = _tree_bytes(_RAW_DIR)
    if after <= before:
        return
    session.config.stash_raw_bytes_grew = after - before  # type: ignore[attr-defined]
    print(
        f"\n\nERROR: data/raw/ grew by {after - before:,} bytes during this run "
        f"({before:,} -> {after:,}). Some test fetched an input that a clean "
        "clone does not have. CHARTER §4b; this is WFG-139, and the socket "
        "guard in tests/conftest.py did not see it, so the path used is one the "
        "guard cannot reach — say which, in writing, before removing this check."
    )
    session.exitstatus = 1
