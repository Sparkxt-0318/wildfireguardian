"""Default workspace locations shared by data and command workflows.

Installed wheels contain code only. Supply explicit data and checkpoint paths
when the installation does not sit next to this workspace's data and runs.
"""
from pathlib import Path
import hashlib

SOURCE_ROOT = Path(__file__).resolve().parent
WORKSPACE = SOURCE_ROOT.parent
DATA = WORKSPACE / "data"
DATA_ROOT = DATA / "environment"
RUNS = WORKSPACE / "runs"
DEMOS = WORKSPACE / "demonstration"
DEFAULT_CHECKPOINT = (
    RUNS / "20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
)


def resolve_recorded_path(value: str | Path) -> Path:
    """Locate this workspace's relocated files without rewriting saved records.

    Existing paths and paths belonging to other workspaces retain their original
    meaning. Only the removed local package layout maps to the new directories.
    Callers still validate the saved content hashes and experiment contracts.
    """
    path = Path(value).expanduser()
    if path.exists():
        return path
    local = path
    if path.is_absolute():
        try:
            local = path.relative_to(WORKSPACE)
        except ValueError:
            return path
    replacements = (
        (Path("wildfire_burned_area_hourly/probability_model/training_runs"), RUNS),
        (Path("wildfire_burned_area_hourly/environmental_data"), DATA_ROOT),
        (Path("wildfire_burned_area_hourly/regions"), DATA / "regions"),
        (Path("wildfire_burned_area_hourly/bitmaps"), DATA / "bitmaps"),
        (Path("wildfire_burned_area_hourly/sources"), DATA / "sources"),
        (Path("wildfire_burned_area_hourly/records"), DATA / "records"),
    )
    for old, new in replacements:
        try:
            return new / local.relative_to(old)
        except ValueError:
            continue
    return path


def resolve_source_root(metadata: dict, *, data_root: str | Path | None = None) -> Path:
    """Locate cached inputs by their saved content hashes after a checkout move.

    An explicit override or an existing recorded directory remains authoritative.
    A missing directory from an older checkout can use the current default only
    when every saved source file has exactly the recorded bytes and SHA-256.
    """
    if data_root is not None:
        return resolve_recorded_path(data_root)
    recorded = resolve_recorded_path(metadata["data_root"])
    if recorded.is_dir() or not DATA_ROOT.is_dir():
        return recorded
    sources = metadata.get("source_files")
    if not isinstance(sources, list) or not sources:
        return recorded
    for source in sources:
        relative = Path(source["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe source-file path in cache metadata")
        path = DATA_ROOT / relative
        if not path.is_file():
            raise ValueError(f"Source integrity mismatch: {path}")
        if "bytes" in source and path.stat().st_size != source["bytes"]:
            raise ValueError(f"Source integrity mismatch: {path}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"Source integrity mismatch: {path}")
    return DATA_ROOT
