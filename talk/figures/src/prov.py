"""Provenance: read result files and record where every printed or plotted number comes from.

Every figure script creates one Ledger, reads values through it, and saves build/<code>_sources.json.
make_docs.py turns those files into SOURCES.md.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from style import BUILD, REPO


def _run(args, cwd=REPO):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True).stdout


def git_show(path, ref=None, repo=REPO):
    """Bytes of a committed file. ref=None reads the commit checked out here (HEAD)."""
    return _run(["git", "show", f"{ref or 'HEAD'}:{path}"], cwd=repo)


def last_commit(path, ref=None, repo=REPO):
    out = _run(["git", "log", "-1", "--format=%h", ref or "HEAD", "--", path], cwd=repo)
    return out.decode().strip() or "uncommitted"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Ledger:
    def __init__(self, code, title):
        self.code = code
        self.title = title
        self.rows = []
        self.notes = []

    # -------- reading
    def json(self, path, ref=None, repo=REPO):
        return json.loads(git_show(path, ref, repo))

    def text(self, path, ref=None, repo=REPO):
        return git_show(path, ref, repo).decode()

    def src_id(self, path, ref=None, repo=REPO):
        """How a file is identified in SOURCES.md: repo, ref, commit hash (or SHA-256 outside this repository)."""
        repo = Path(repo)
        if repo == REPO:
            try:
                h = last_commit(path, ref, repo)
            except subprocess.CalledProcessError:
                h = "not in git"
            return {"repo": "wildfireguardian", "ref": ref or "talk/figures (= origin/Main 5ff9aa90)", "commit": h}
        h = "sha256:" + sha256_file(repo / path)[:16]
        return {"repo": str(repo), "ref": "file on disk (read only)", "commit": h}

    def local_text(self, path, repo):
        return (Path(repo) / path).read_text()

    # -------- recording
    def add(self, label, value, *, file, field, n=None, ref=None, repo=REPO,
            expected=None, unit="", shown=None, note="", commit=None, repo_name=None):
        """Record one number shown on the figure. `shown` is the text as printed.
        commit/repo_name override the identification (for files fetched from another repository)."""
        if commit:
            sid = {"repo": repo_name, "ref": ref or "main", "commit": commit}
        else:
            sid = self.src_id(file, ref, repo)
        row = dict(label=label, value=value, unit=unit, shown=shown, n=n, file=file,
                   field=field, expected=expected, note=note, **sid)
        self.rows.append(row)
        return value

    def note(self, text):
        self.notes.append(text)

    def save(self):
        out = BUILD / f"{self.code}_sources.json"
        out.write_text(json.dumps({"code": self.code, "title": self.title,
                                   "rows": self.rows, "notes": self.notes},
                                  indent=1, ensure_ascii=False, default=str))
        return out
