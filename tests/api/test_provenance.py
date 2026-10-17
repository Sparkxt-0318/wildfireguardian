"""Provenance git identity: trust git only for the repository's own work tree."""
import subprocess

from api.provenance import git_identity


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _repo(path):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "-c", "commit.gpgsign=false",
         "commit", "-q", "--allow-empty", "-m", "x")
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def test_own_checkout_reports_its_commit(tmp_path, monkeypatch):
    monkeypatch.delenv("WFG_API_GIT_COMMIT", raising=False)
    head = _repo(tmp_path / "repo")
    assert git_identity(tmp_path / "repo") == (head, False)


def test_copy_inside_another_checkout_does_not_borrow_its_commit(tmp_path, monkeypatch):
    _repo(tmp_path / "outer")
    copy = tmp_path / "outer" / "sub" / "copy"
    copy.mkdir(parents=True)
    monkeypatch.delenv("WFG_API_GIT_COMMIT", raising=False)
    assert git_identity(copy) == ("unknown", None)
    monkeypatch.setenv("WFG_API_GIT_COMMIT", "abc123")
    assert git_identity(copy) == ("abc123", None)


def test_env_value_never_overrides_a_real_checkout(tmp_path, monkeypatch):
    head = _repo(tmp_path / "repo")
    monkeypatch.setenv("WFG_API_GIT_COMMIT", "abc123")
    assert git_identity(tmp_path / "repo")[0] == head
