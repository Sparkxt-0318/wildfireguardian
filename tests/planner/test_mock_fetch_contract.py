"""Tests of planner/scripts/fetch_contract.sh in throwaway git repositories (no network, the real repo is untouched).

An "upstream" repository plays origin with a feat/api branch holding contracts/wfg_api_v1.yaml and CHANGELOG.md; a
clone on branch main runs a copy of the script. Checked: the copy, its first-line source comment and SOURCE_COMMIT;
an unchanged rerun; --check exit 4 and the diff summary after an upstream change; exit 3 when only another head has
the contract; exit 2 when no head has it; the working branch is never changed.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "planner" / "scripts" / "fetch_contract.sh"
CONTRACT_COPY = ROOT / "planner" / "contract" / "wfg_api_v1.yaml"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None, reason="needs git and bash")

ENV = dict(os.environ, GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@example.invalid", GIT_COMMITTER_NAME="test",
           GIT_COMMITTER_EMAIL="test@example.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
           GIT_TERMINAL_PROMPT="0")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout.strip()


def contract_text(version: str = "1.0.0") -> str:
    """The real contract copy (whatever version it is now) with its info.version set to ``version``."""
    body = CONTRACT_COPY.read_text(encoding="utf-8").split("\n", 1)[1]     # drop the copy's source comment
    info_version = re.compile(r"^(info:\n(?:  .*\n)*?)  version: [^\n]+\n", re.M)
    assert info_version.search(body), "contract copy has no info.version line"
    return info_version.sub(lambda m: "%s  version: %s\n" % (m.group(1), version), body, count=1)


CHANGELOG_V1 = "# changelog\n\n## v1.0.0 — initial contract\n"
CHANGELOG_V11 = CHANGELOG_V1 + "\n## v1.1 — additive\n\n- new optional field\n"


@pytest.fixture()
def repos(tmp_path):
    up = tmp_path / "upstream"
    up.mkdir()
    git(up, "init", "-q", "-b", "main")
    (up / "README.md").write_text("upstream\n")
    git(up, "add", ".")
    git(up, "commit", "-qm", "main")
    git(up, "checkout", "-q", "-b", "feat/api")
    (up / "contracts").mkdir()
    (up / "contracts" / "wfg_api_v1.yaml").write_text(contract_text("1.0.0"), encoding="utf-8")
    (up / "contracts" / "CHANGELOG.md").write_text(CHANGELOG_V1, encoding="utf-8")
    git(up, "add", ".")
    git(up, "commit", "-qm", "contract v1.0")
    git(up, "checkout", "-q", "main")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(up), str(clone)], env=ENV, check=True, capture_output=True)
    (clone / "planner" / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, clone / "planner" / "scripts" / "fetch_contract.sh")
    return up, clone


def run(clone: Path, *args: str):
    p = subprocess.run(["bash", str(clone / "planner" / "scripts" / "fetch_contract.sh"), *args], cwd=clone, env=ENV,
                       capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


def test_script_is_executable():
    assert os.access(SCRIPT, os.X_OK)
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0


def test_copy_rerun_and_change_detection(repos):
    up, clone = repos
    code, out = run(clone)
    assert code == 0, out
    dest = clone / "planner" / "contract"
    commit = git(up, "rev-parse", "feat/api")
    first, rest = (dest / "wfg_api_v1.yaml").read_text(encoding="utf-8").split("\n", 1)
    assert first == ("# Fetched from origin/feat/api commit %s (contracts/wfg_api_v1.yaml). Do not edit; re-run "
                     "planner/scripts/fetch_contract.sh." % commit)
    assert rest == contract_text("1.0.0")
    assert (dest / "CHANGELOG.md").read_text(encoding="utf-8") == CHANGELOG_V1
    assert (dest / "SOURCE_COMMIT").read_text() == commit + "\n"
    assert git(clone, "branch", "--show-current") == "main"

    code, out = run(clone)
    assert code == 0 and "content unchanged" in out and "is current" in out, out
    code, out = run(clone, "--check")
    assert code == 0, out

    # upstream publishes v1.1
    git(up, "checkout", "-q", "feat/api")
    (up / "contracts" / "wfg_api_v1.yaml").write_text(contract_text("1.1.0"), encoding="utf-8")
    (up / "contracts" / "CHANGELOG.md").write_text(CHANGELOG_V11, encoding="utf-8")
    git(up, "commit", "-qam", "contract v1.1")
    git(up, "checkout", "-q", "main")
    new_commit = git(up, "rev-parse", "feat/api")

    code, out = run(clone, "--check")
    assert code == 4, out
    assert "info.version: 1.0.0 -> 1.1.0" in out
    assert "## v1.1" in out and "CHANGELOG.md gained a version" in out
    assert (dest / "SOURCE_COMMIT").read_text() == commit + "\n"          # --check writes nothing

    code, out = run(clone)
    assert code == 0, out
    assert (dest / "SOURCE_COMMIT").read_text() == new_commit + "\n"
    assert "version: 1.1.0" in (dest / "wfg_api_v1.yaml").read_text(encoding="utf-8")
    assert git(clone, "branch", "--show-current") == "main"
    assert git(clone, "status", "--porcelain", "--untracked-files=no") == ""


def test_contract_only_on_another_head_exits_3(repos):
    up, clone = repos
    git(up, "branch", "-m", "feat/api", "api-elsewhere")
    git(clone, "fetch", "-q", "origin")
    code, out = run(clone)
    assert code == 3, out
    assert "found   api-elsewhere" in out
    assert not (clone / "planner" / "contract").exists()


def test_no_head_with_contract_exits_2(repos):
    up, clone = repos
    git(up, "branch", "-D", "feat/api")
    code, out = run(clone)
    assert code == 2, out
    assert "no head of origin contains contracts/wfg_api_v1.yaml" in out
    assert not (clone / "planner" / "contract").exists()
