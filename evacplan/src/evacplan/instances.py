"""The frozen ``dev``/``test`` split (``evacplan/instances/SPLIT.json``) and the instance cache.

``SPLIT.json`` lists every instance id with its generator, generator version, config (with the
seed), a SYNTHETIC flag, a few size statistics and a fingerprint (sha256 of the instance JSON, the
hazard meta and the hazard arrays). Instances are never committed: they regenerate
deterministically into ``evacplan/cache/instances/<id>/`` (git-ignored) as ``instance.json`` plus
the scenario-set folder ``hazard/``. A regenerated instance whose fingerprint differs from the
split is refused (generator drift: the frozen instances would silently change).

Program rule 5: the split is frozen before any method runs; ``test`` is touched only at
milestones, after Siyeong approves (the harness refuses it otherwise).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

import hazard_contract as hc

from .schema import Instance, load_instance, load_scenario_set

EVACPLAN_ROOT = Path(__file__).resolve().parents[2]
SPLIT_PATH = EVACPLAN_ROOT / "instances" / "SPLIT.json"
CACHE_DIR = EVACPLAN_ROOT / "cache" / "instances"
SPLIT_SCHEMA = "evacplan.split/1"
SETS = ("dev", "test")


class GeneratorDrift(RuntimeError):
    """A regenerated instance does not match the fingerprint frozen in the split."""


# ------------------------------------------------------------------------------ fingerprint
def _canonical(model) -> bytes:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()


def fingerprint(instance: Instance, hazard: hc.ScenarioSet) -> str:
    """sha256 over the canonical JSON of the instance and of the hazard meta, and the hazard
    arrays (float64 little-endian, C order)."""
    h = hashlib.sha256()
    for part in (_canonical(instance), _canonical(hazard.meta)):
        h.update(len(part).to_bytes(8, "little"))
        h.update(part)
    for a in (hazard.ignite_s, hazard.extinguish_s):
        h.update(np.ascontiguousarray(a, dtype="<f8").tobytes())
    h.update(np.ascontiguousarray(hazard.supported, dtype=np.uint8).tobytes())
    return "sha256:" + h.hexdigest()


# ------------------------------------------------------------------------------------ split
class SplitEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    generator: str
    generator_version: str
    config: dict[str, Any]
    synthetic: bool
    fingerprint: str
    stats: dict[str, Any] = Field(default_factory=dict)

    @property
    def label(self) -> str:
        return "SYNTHETIC" if self.synthetic else ""


class Split(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(SPLIT_SCHEMA, alias="schema")
    frozen: str = Field(description="date the split was frozen (before any method ran)")
    note: str = ""
    sets: dict[str, list[SplitEntry]]

    def entries(self, name: str) -> list[SplitEntry]:
        if name not in self.sets:
            raise KeyError(f"unknown set {name!r}; the split has {sorted(self.sets)}")
        return list(self.sets[name])

    def set_of(self, instance_id: str) -> str:
        for name, entries in self.sets.items():
            if any(e.id == instance_id for e in entries):
                return name
        raise KeyError(instance_id)

    def ids(self, name: str) -> list[str]:
        return [e.id for e in self.entries(name)]


def load_split(path=SPLIT_PATH) -> Split:
    return Split.model_validate_json(Path(path).read_text())


def write_split(split: Split, path=SPLIT_PATH, *, overwrite: bool = False) -> Path:
    p = Path(path)
    if p.exists() and not overwrite:
        raise FileExistsError(f"{p} exists: the split is frozen (changing it needs Siyeong's approval)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(split.model_dump(by_alias=True), indent=1) + "\n")
    return p


def canonical_sets(split: Split) -> str:
    """Canonical JSON of the sets (what the frozen-split test pins)."""
    return json.dumps(split.model_dump(by_alias=True)["sets"], sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------------------- generation
def generate_entry(entry: SplitEntry):
    """Regenerate one split entry (dispatch on its generator and version)."""
    from .generators import synthetic as syn
    if entry.generator == syn.GENERATOR:
        if entry.generator_version != syn.GENERATOR_VERSION:
            raise GeneratorDrift(f"{entry.id}: frozen with {entry.generator_version}, this code is "
                                 f"{syn.GENERATOR_VERSION}")
        gen = syn.generate(syn.SyntheticConfig.model_validate(entry.config))
        if gen.instance_id != entry.id:
            raise GeneratorDrift(f"{entry.id}: config now yields id {gen.instance_id}")
        return gen
    raise ValueError(f"{entry.id}: unknown generator {entry.generator!r}")


def make_entry(gen) -> SplitEntry:
    """Split entry for a freshly generated instance (used once, to freeze the split)."""
    from .generators import synthetic as syn
    return SplitEntry(id=gen.instance_id, generator=syn.GENERATOR, generator_version=syn.GENERATOR_VERSION,
                      config=gen.config.model_dump(), synthetic=bool(gen.instance.synthetic),
                      fingerprint=gen.fingerprint(), stats=syn.summary(gen))


def default_split_configs() -> dict[str, list]:
    """The frozen mix: per set 4 S + 4 M + 2 L (grid and random geometric roads, two tightness
    levels for S and M, medium for L); dev seeds 101-110, test seeds 201-210 (disjoint)."""
    from .generators.synthetic import SyntheticConfig
    mix = [("S", "grid", 0.25), ("S", "geo", 0.25), ("S", "grid", 0.75), ("S", "geo", 0.75),
           ("M", "grid", 0.25), ("M", "geo", 0.25), ("M", "grid", 0.75), ("M", "geo", 0.75),
           ("L", "grid", 0.5), ("L", "geo", 0.5)]
    return {name: [SyntheticConfig(size=s, graph=g, tightness=t, seed=base + i) for i, (s, g, t) in enumerate(mix)]
            for name, base in (("dev", 101), ("test", 201))}


def build_split(configs: dict[str, list], *, frozen: str, note: str = "") -> Split:
    from .generators.synthetic import generate
    sets = {name: [make_entry(generate(c)) for c in cfgs] for name, cfgs in configs.items()}
    return Split(schema=SPLIT_SCHEMA, frozen=frozen, note=note, sets=sets)


# ------------------------------------------------------------------------------------ cache
def cached_paths(entry: SplitEntry, cache_dir=CACHE_DIR) -> tuple[Path, Path]:
    d = Path(cache_dir) / entry.id
    return d / "instance.json", d / "hazard"


def _load(entry: SplitEntry, cache_dir) -> tuple[Instance, hc.ScenarioSet] | None:
    inst_path, hz = cached_paths(entry, cache_dir)
    if not (inst_path.is_file() and hz.is_dir()):
        return None
    try:
        inst = load_instance(inst_path)
        return inst, load_scenario_set(inst)
    except Exception:  # noqa: BLE001 - a broken cache entry is simply regenerated
        return None


def materialize(entry: SplitEntry, cache_dir=CACHE_DIR, *, verify: bool = True) -> Path:
    """Make sure ``cache_dir/<id>/`` holds this entry (regenerating it if needed) and return the
    path of its ``instance.json``. Raises :class:`GeneratorDrift` if the instance no longer
    matches its frozen fingerprint."""
    inst_path, _ = cached_paths(entry, cache_dir)
    got = _load(entry, cache_dir)
    if got is not None and (not verify or fingerprint(*got) == entry.fingerprint):
        return inst_path
    gen = generate_entry(entry)
    fp = gen.fingerprint()
    if verify and fp != entry.fingerprint:
        raise GeneratorDrift(f"{entry.id}: regenerated fingerprint {fp} != frozen {entry.fingerprint}; the "
                             "generator (or numpy) changed. Do not run methods on a drifted split.")
    target = inst_path.parent
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{entry.id}.", dir=target.parent))
    try:
        gen.write(tmp, overwrite=True)
        if target.exists():
            shutil.rmtree(target)
        tmp.rename(target)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return inst_path


def load_entry(entry: SplitEntry, cache_dir=CACHE_DIR, *, verify: bool = True) -> tuple[Instance, hc.ScenarioSet]:
    """The instance and its scenario set, from the cache (materialized on demand)."""
    path = materialize(entry, cache_dir, verify=verify)
    inst = load_instance(path)
    return inst, load_scenario_set(inst)
