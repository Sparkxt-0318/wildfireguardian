"""Receipt and input helpers for the worker."""
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    with Path(path).open("x") as file:
        json.dump(obj, file, indent=2, allow_nan=False, default=str)
