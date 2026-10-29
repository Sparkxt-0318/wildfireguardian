"""Track 1B changes to models.py, train.py and evaluate.py are additive.

Proof by construction: models.py starts with the released bytes; every other
released top-level definition of train.py and evaluate.py is byte-identical;
the default command lines reach the released functions with exactly the
released arguments.
"""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

import importlib

import wildfire
from wildfire.metrics import add_categorical_balance_arguments

# The package namespace exports a function named ``train``; import the modules explicitly.
train_module = importlib.import_module("wildfire.train")
evaluate_module = importlib.import_module("wildfire.evaluate")
RELEASED = json.loads((Path(__file__).with_name("released_definitions.json")).read_text())
SOURCE = Path(wildfire.__file__).parent
CHANGED = {"train": {"parser", "train_main"}, "evaluate": {"kernels_main"}}


def _definitions(path):
    source = path.read_text()
    tree = ast.parse(source)
    return {node.name: hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
            for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


def test_models_module_is_the_released_module_plus_appended_classes():
    data = (SOURCE / "models.py").read_bytes()
    released = RELEASED["models"]
    assert hashlib.sha256(data[:released["bytes"]]).hexdigest() == released["sha256"]
    current = _definitions(SOURCE / "models.py")
    for name, digest in released["definitions"].items():
        assert current[name] == digest, name


def test_train_and_evaluate_definitions_are_unchanged_except_entry_points():
    for module in ("train", "evaluate"):
        current = _definitions(SOURCE / f"{module}.py")
        for name, digest in RELEASED[module]["definitions"].items():
            if name not in CHANGED[module]:
                assert current[name] == digest, (module, name)


def _released_train_parser():
    """The released ``train.parser`` body, verbatim."""
    result = argparse.ArgumentParser(description=train_module.__doc__)
    result.add_argument("--data-dir", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--epochs", type=int, default=30)
    result.add_argument("--patience", type=int, default=6)
    result.add_argument("--batch-size", type=int, default=1024)
    result.add_argument("--hidden-channels", type=int, default=16)
    result.add_argument("--learning-rate", type=float, default=1e-3)
    result.add_argument("--weight-decay", type=float, default=1e-4)
    result.add_argument("--seed", type=int, default=7)
    result.add_argument("--threads", type=int, default=4)
    result.add_argument("--device", default="cpu")
    add_categorical_balance_arguments(result)
    return result


def test_default_train_command_reaches_released_trainer_with_released_arguments(monkeypatch):
    argv = ["wildfire train", "--data-dir", "cache", "--output-dir", "out", "--epochs", "3"]
    expected = vars(_released_train_parser().parse_args(argv[1:]))
    captured = {}
    monkeypatch.setattr(train_module, "train", lambda args: captured.setdefault("args", args))
    monkeypatch.setattr(train_module, "train_perimeter", lambda args: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(sys, "argv", argv)
    train_module.train_main()
    assert vars(captured["args"]) == expected


def test_default_evaluate_command_reaches_released_comparison(monkeypatch):
    calls = []
    monkeypatch.setattr(evaluate_module, "evaluate_runs", lambda *a: calls.append(a))
    monkeypatch.setattr(sys, "argv", ["wildfire evaluate", "--run-dir", "a", "--run-dir", "b", "--output-dir", "o"])
    evaluate_module.kernels_main()
    assert calls == [([Path("a"), Path("b")], Path("o"), "cpu")]
