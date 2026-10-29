"""Append-only JSON-lines store of finished work units, so that an interrupted run resumes without redoing them.

Each line is {"key": [...], "value": ...}. Keys are lists of JSON scalars. The store lives in binding/work/ (ignored
by git); deleting it forces a full rerun. Results do not depend on resumption because every unit is deterministic
(timings of resumed units are the timings of their original execution).
"""
from __future__ import annotations

import json
from pathlib import Path


class WorkStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[json.dumps(rec["key"])] = rec["value"]

    def get(self, key, default=None):
        return self.data.get(json.dumps(list(key)), default)

    def has(self, key):
        return json.dumps(list(key)) in self.data

    def put(self, key, value):
        k = json.dumps(list(key))
        self.data[k] = value
        with open(self.path, "a") as f:
            f.write(json.dumps({"key": list(key), "value": value}, default=str) + "\n")
