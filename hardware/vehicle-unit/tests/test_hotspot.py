"""system/hotspot.sh against a fake ``nmcli`` (finding VU-R9). Nothing here touches a real NetworkManager.

Checks: a bad passphrase changes nothing; the passphrase never appears on an nmcli command line; the old profile is
deleted only after the new one is up; a failed activation keeps (and re-activates) the old profile.
"""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "system" / "hotspot.sh"
BASH = shutil.which("bash")

FAKE_NMCLI = r"""#!/bin/sh
echo "$*" >> "$NMCLI_LOG"
case "$*" in
  "-t -f NAME,UUID con show") printf 'other:1111\nwfgvu-hotspot:old-uuid-0001\n' ;;
  "con up uuid old-uuid-0001") exit 0 ;;
  "con up uuid "*) [ "${NMCLI_UP_FAILS:-0}" = 1 ] && exit 4; exit 0 ;;
esac
exit 0
"""

pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")


def run(tmp_path, psk, up_fails=False):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    nm = bindir / "nmcli"
    nm.write_text(FAKE_NMCLI)
    nm.chmod(0o755)
    log = tmp_path / "nmcli.log"
    log.write_text("")
    nm_dir = tmp_path / "nm"
    env = dict(os.environ, PATH="%s:%s" % (bindir, os.environ.get("PATH", "/usr/bin:/bin")), NMCLI_LOG=str(log),
               WFGVU_PSK=psk, WFGVU_NM_DIR=str(nm_dir), WFGVU_PSK_FILE=str(tmp_path / "none"),
               NMCLI_UP_FAILS="1" if up_fails else "0")
    r = subprocess.run([BASH, str(SCRIPT), "up"], env=env, capture_output=True, text=True, timeout=30)
    calls = [ln for ln in log.read_text().splitlines() if ln]
    files = sorted(nm_dir.glob("*")) if nm_dir.exists() else []
    return r, calls, files


@pytest.mark.parametrize("psk", ["short7c", "x" * 64, "café-passphrase", "tab\there-pass", "back\\slash-pass",
                                 " leading-space"])
def test_bad_passphrase_changes_nothing(tmp_path, psk):
    r, calls, files = run(tmp_path, psk)
    assert r.returncode == 2, r.stderr
    assert not any("delete" in c or "load" in c or "up" in c.split() for c in calls)
    assert files == []


def test_up_swaps_profiles_without_passphrase_on_argv(tmp_path):
    psk = "Corr3ct horse battery!"
    r, calls, files = run(tmp_path, psk)
    assert r.returncode == 0, r.stderr + r.stdout
    assert not any(psk in c for c in calls)                     # never on an nmcli command line
    assert len(files) == 1 and not files[0].name.startswith(".")
    assert stat.S_IMODE(files[0].stat().st_mode) == 0o600
    text = files[0].read_text()
    assert "psk=%s\n" % psk in text and "mode=ap" in text and "key-mgmt=wpa-psk" in text
    i_load = next(i for i, c in enumerate(calls) if c.startswith("con load"))
    i_up = next(i for i, c in enumerate(calls) if c.startswith("con up uuid") and "old-uuid" not in c)
    i_del = next(i for i, c in enumerate(calls) if c == "con delete uuid old-uuid-0001")
    i_ren = next(i for i, c in enumerate(calls) if c.startswith("con modify uuid") and "connection.id wfgvu-hotspot"
                 in c)
    assert i_load < i_up < i_del < i_ren                       # old profile deleted only after the new one is up


def test_failed_activation_keeps_old_profile(tmp_path):
    r, calls, files = run(tmp_path, "another-good-pass", up_fails=True)
    assert r.returncode == 1
    assert "con delete uuid old-uuid-0001" not in calls
    assert "con up uuid old-uuid-0001" in calls                # old hotspot re-activated
    assert any(c.startswith("con delete uuid") and "old-uuid" not in c for c in calls)
    assert files == []                                          # new keyfile removed
