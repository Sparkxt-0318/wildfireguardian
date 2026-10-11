"""Run the multiscale search on a copied checkout using CPU, MPS, or CUDA.

Defaults locate the original prepared cache and environmental data relative to
this module, not the original machine's absolute paths. A verified cache clone
changes only the source-data root. Each root gets its own clone, and default
experiment directories are separate for every execution device and stage type.
The frozen training implementation and existing experiment files stay intact.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile

import torch

from . import kernel_search_multiscale as search
from .relocate_search_cache import relocate_cache
from .runtime import choose_device

PACKAGE = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = PACKAGE.parent / "environmental_data"


def parser():
    result = search.parser()
    result.description = __doc__
    result.set_defaults(output=None)
    for action in result._actions:
        if action.dest == "device":
            action.help = "auto selects available CUDA, then MPS, then CPU; resume requires the same training device"
        elif action.dest == "cache":
            action.help = "Original unmodified full 9x9 prepared_all cache; a relocated copy is created automatically"
        elif action.dest == "output":
            action.help = "Experiment directory; defaults to a separate portable directory for the selected device"
    result.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT,
                        help="Complete original environmental data; defaults beside probability_model in this checkout")
    result.add_argument("--portable-cache", type=Path,
                        help="Optional destination for the relocated cache; defaults to a separate directory for this data-root path")
    result.add_argument("--check-only", action="store_true",
                        help="Verify device, relocation, and search setup in a temporary output without training")
    return result


def prepare_args(args):
    """Resolve host paths/device and verify inputs before dispatching training."""
    if args.epochs < 1 or args.finalist_epochs < args.epochs or args.threads < 1:
        raise ValueError("Epochs/threads must be positive and finalist budget must include initial training")
    if args.device == "auto":
        args.device = ("cuda" if torch.cuda.is_available() else
                       "mps" if torch.backends.mps.is_available() else "cpu")
    # Explicit unavailable devices fail before any cache or output is created.
    choose_device(args.device)
    args.data_root = args.data_root.resolve()
    source = args.cache.resolve()
    if args.portable_cache is None:
        root_id = hashlib.sha256(str(args.data_root).encode("utf-8")).hexdigest()[:16]
        args.portable_cache = source.parent / "prepared_portable" / root_id
    else:
        args.portable_cache = args.portable_cache.resolve()
    if args.output is None:
        run_name = "kernel_smoke" if args.stage == "smoke" else "kernel_search"
        cache_id = hashlib.sha256(str(args.portable_cache.resolve()).encode("utf-8")).hexdigest()[:16]
        device_label = args.device.replace(":", "-")
        args.output = search.RUNS / f"20261009_multiscale_{run_name}_{device_label}_portable" / cache_id
    else:
        args.output = args.output.resolve()
    print(f"Execution device: {args.device}", flush=True)
    record = relocate_cache(source, args.portable_cache, args.data_root)
    args.cache = args.portable_cache
    print(f"Cache {record['status']}: {args.cache}", flush=True)
    print(f"Verified original environmental sources: {record['verified_source_files']}", flush=True)
    print(f"Experiment output: {args.output}", flush=True)
    return args


def main():
    args = prepare_args(parser().parse_args())
    if args.check_only:
        # A preflight must not bind the requested experiment output or conflict
        # with smoke's reduced epoch budget. Only the verified cache clone is
        # retained; the trial protocol and source snapshot are temporary.
        trial_args = copy.copy(args)
        with tempfile.TemporaryDirectory(prefix="wildfire-search-preflight-") as directory:
            trial_args.output = Path(directory) / "preflight"
            protocol = search.setup_from_args(trial_args)
        print(json.dumps(dict(status="passed", device=args.device,
                              candidate_count=len(protocol["candidates"]),
                              verified_source_files=protocol["verified_source_files"],
                              cache=str(args.cache), intended_output=str(args.output),
                              training_started=False, experiment_output_modified=False), indent=2))
        return
    stages = {"run": search.run_all, "smoke": search.smoke, "train": search.train_search,
              "forests": search.forest_search, "finalize": search.finalize}
    stages[args.stage](args)


if __name__ == "__main__":
    main()
