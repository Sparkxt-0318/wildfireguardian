"""Shared cross-validation splitters for the WildfireGuardian research program.

Owner: A6, the validation agent. No modeling agent writes its own splitter.
The reason is not tidiness. A split is the single easiest place to make a weak
result look strong, and the choice is usually made once, quietly, by the person
who wants the result. So the splits live here, they are deterministic, and they
refuse rather than warn.

Four schemes, one per way a leak arrives in this program:

``leave_one_fire_out``
    One Korean fire is held out per fold. It REFUSES by default when the
    held-out fire shares a fire complex with a training fire, because that is
    exactly the leak the repository already measured on the 2025 Yeongnam pair
    (see ``docs/leakfree_fold.md``: the held-out ROC-AUC was 0.9403 with the
    co-located fire in training and 0.8691 without it).

``leave_one_complex_out``
    The same, with the complex as the unit. This is the default for the roads
    direction. It refuses any fire id it has never heard of, because a leak
    most often enters as a new spelling of a fire that is already in the set.

``spatial_block_cv``
    Square blocks in projected metres, with an optional buffer band that is
    removed from training. This is the only admissible scheme for the landslide
    direction: slope units a few hundred metres apart share a storm, a geology
    and a fire, so a random split is a near-duplicate split.

``forward_chaining_by_year``
    Train on the past, test on the next year. This is the only admissible
    scheme for the suppression direction, because the Korean suppression record
    spans decades of changing doctrine and fleet, and a random split lets a
    later policy predict an earlier fire.

Every splitter returns :class:`Split` objects and every :class:`Split` can be
re-audited after the fact with :func:`audit_split`. A number reported to A6
carries its split fingerprint, so the split that produced it is recoverable.

Coordinates are projected metres (EPSG:5179 is the program default). Latitude
and longitude are refused unless the caller says so explicitly, because a block
size of 5000 in degrees is a silent whole-country block.

No foreign data is in scope here. These splitters carry no country logic; the
Korea-only rule is enforced at the registry, not at the splitter.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

__all__ = [
    "LeakageRefusal",
    "Split",
    "canonical_fire_id",
    "complex_of",
    "leave_one_fire_out",
    "leave_one_complex_out",
    "spatial_block_cv",
    "forward_chaining_by_year",
    "assert_group_disjoint",
    "assert_min_separation",
    "assert_time_ordered",
    "audit_split",
    "primary_split_spec",
    "FIRE_COMPLEXES",
    "PRIMARY_SPLITS",
]


class LeakageRefusal(Exception):
    """Raised instead of returning a split that would leak.

    This is deliberately not a warning. A warning is something a modeling agent
    filters out of its log; a refusal stops the run.
    """


# --------------------------------------------------------------------- ids --

#: Spellings seen in this repository and in the program brief, mapped to one
#: canonical id per fire. Korean and romanised spellings both resolve here.
#: Adding a fire means adding it here AND to :data:`FIRE_COMPLEXES`.
_FIRE_ALIASES: dict[str, str] = {
    "goseong2019": "goseong_2019",
    "고성2019": "goseong_2019",
    "고성속초2019": "goseong_2019",
    "uljin2022": "uljin_samcheok_2022",
    "uljinsamcheok2022": "uljin_samcheok_2022",
    "울진2022": "uljin_samcheok_2022",
    "울진삼척2022": "uljin_samcheok_2022",
    "miryang2022": "miryang_2022",
    "밀양2022": "miryang_2022",
    "gangneung2023": "gangneung_2023",
    "강릉2023": "gangneung_2023",
    "hongseong2023": "hongseong_2023",
    "홍성2023": "hongseong_2023",
    "uiseong2025": "uiseong_andong_2025",
    "uiseongandong2025": "uiseong_andong_2025",
    "의성2025": "uiseong_andong_2025",
    "의성안동2025": "uiseong_andong_2025",
    "andong2025": "uiseong_andong_2025",
    "안동2025": "uiseong_andong_2025",
    "yeongdeok2025": "yeongdeok_2025",
    "영덕2025": "yeongdeok_2025",
    "sancheong2025": "sancheong_2025",
    "산청2025": "sancheong_2025",
    "sancheonghadong2025": "sancheong_2025",
    "산청하동2025": "sancheong_2025",
}

#: Canonical fire id -> complex id. The one grouping that is not the identity
#: is the 2025 Yeongnam pair, and it is the repository's own rule
#: (``docs/benchmark/K_SPREAD_2025.md`` section 2, ``docs/leakfree_fold.md``):
#: Yeongdeok 2025 and Uiseong-Andong 2025 are one complex and are never on
#: opposite sides of a split.
FIRE_COMPLEXES: dict[str, str] = {
    "goseong_2019": "goseong_2019",
    "uljin_samcheok_2022": "uljin_samcheok_2022",
    "miryang_2022": "miryang_2022",
    "gangneung_2023": "gangneung_2023",
    "hongseong_2023": "hongseong_2023",
    "uiseong_andong_2025": "yeongnam_2025",
    "yeongdeok_2025": "yeongnam_2025",
    "sancheong_2025": "sancheong_2025",
}

_NORMALISE = re.compile(r"[\s_\-·・.,()]+")


def canonical_fire_id(raw: str) -> str:
    """Resolve one spelling of a fire to its canonical id.

    Unknown spellings are returned normalised rather than refused, so that a
    direction can carry fires this module has not met. The refusal happens in
    :func:`complex_of`, where an unregistered fire is a real risk.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise LeakageRefusal("a fire id must be a non-empty string, got %r" % (raw,))
    key = _NORMALISE.sub("", raw.strip().lower())
    return _FIRE_ALIASES.get(key, key)


def complex_of(fire_id: str,
               extra_complexes: Mapping[str, str] | None = None,
               *, strict: bool = True) -> str:
    """Complex id for one fire.

    With ``strict`` (the default) an unregistered fire is refused. That is the
    point: treating an unknown fire as its own complex is how a second spelling
    of an already-present fire ends up on both sides of a split. Register it in
    :data:`FIRE_COMPLEXES` or pass it in ``extra_complexes``.
    """
    fid = canonical_fire_id(fire_id)
    table = dict(FIRE_COMPLEXES)
    if extra_complexes:
        table.update({canonical_fire_id(k): v for k, v in extra_complexes.items()})
    if fid in table:
        return table[fid]
    if strict:
        raise LeakageRefusal(
            "fire %r (normalised %r) is not in the complex registry. Register it "
            "in FIRE_COMPLEXES or pass extra_complexes={%r: '<complex id>'}. An "
            "unregistered fire is refused because a second spelling of a fire "
            "already in the set is the usual way a complex leak enters."
            % (fire_id, fid, fid))
    return fid


# ------------------------------------------------------------------ split --

@dataclass(frozen=True)
class Split:
    """One fold. Indices are positions into the caller's row order."""

    scheme: str
    fold: int
    held_out: str
    train: tuple[int, ...]
    test: tuple[int, ...]
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.train:
            raise LeakageRefusal(
                "fold %d of %s has an empty training set (held out %s)"
                % (self.fold, self.scheme, self.held_out))
        if not self.test:
            raise LeakageRefusal(
                "fold %d of %s has an empty test set (held out %s)"
                % (self.fold, self.scheme, self.held_out))
        overlap = sorted(set(self.train) & set(self.test))
        if overlap:
            raise LeakageRefusal(
                "fold %d of %s puts %d row(s) on both sides, first offenders %r"
                % (self.fold, self.scheme, len(overlap), overlap[:10]))

    def fingerprint(self) -> str:
        """Stable sha256 over the fold's content.

        A number reported to A6 names this string. Two runs that claim the same
        split and print different fingerprints are two different experiments.
        """
        payload = json.dumps(
            {"scheme": self.scheme, "fold": self.fold, "held_out": self.held_out,
             "train": sorted(self.train), "test": sorted(self.test),
             "meta": _jsonable(self.meta)},
            sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def splits_fingerprint(splits: Sequence[Split]) -> str:
    """One sha256 over an ordered list of folds."""
    h = hashlib.sha256()
    for s in splits:
        h.update(s.fingerprint().encode("ascii"))
    return h.hexdigest()


# ------------------------------------------------------------ by-fire CV ---

def _check_ids(fire_ids: Sequence[str]) -> list[str]:
    if not isinstance(fire_ids, (list, tuple)):
        fire_ids = list(fire_ids)
    if len(fire_ids) == 0:
        raise LeakageRefusal("no rows were given, so there is nothing to split")
    return [canonical_fire_id(f) for f in fire_ids]


def leave_one_fire_out(fire_ids: Sequence[str], *,
                       extra_complexes: Mapping[str, str] | None = None,
                       on_complex_overlap: str = "refuse",
                       reason: str | None = None) -> list[Split]:
    """One fold per fire.

    ``on_complex_overlap``:

    ``"refuse"`` (default)
        A fold whose held-out fire shares a complex with a training fire is
        refused, and the message names the offenders. Use
        :func:`leave_one_complex_out` instead.
    ``"declare"``
        The fold is produced, ``reason`` is required and non-empty, and the
        fold carries ``meta["complex_contaminated"] = True`` plus the reason.
        A6 reads that flag; a number from a contaminated fold is reported as
        contaminated or it is not reported.
    """
    if on_complex_overlap not in ("refuse", "declare"):
        raise LeakageRefusal(
            "on_complex_overlap must be 'refuse' or 'declare', got %r" % (on_complex_overlap,))
    if on_complex_overlap == "declare" and not (reason or "").strip():
        raise LeakageRefusal(
            "on_complex_overlap='declare' needs a written reason. A fold that "
            "trains on a fire of the same complex as the held-out fire is a "
            "known leak in this repository, and taking it knowingly is a "
            "decision that has to be recorded, not a default.")

    ids = _check_ids(fire_ids)
    order = sorted(set(ids))
    splits: list[Split] = []
    for k, fire in enumerate(order):
        test = tuple(i for i, f in enumerate(ids) if f == fire)
        train = tuple(i for i, f in enumerate(ids) if f != fire)
        if not train:
            raise LeakageRefusal(
                "holding out %s leaves no training rows; leave-one-fire-out "
                "needs at least two fires" % fire)
        held_cx = complex_of(fire, extra_complexes)
        siblings = sorted({f for f in order
                           if f != fire and complex_of(f, extra_complexes) == held_cx})
        meta: dict = {"fire": fire, "complex": held_cx}
        if siblings:
            if on_complex_overlap == "refuse":
                raise LeakageRefusal(
                    "leave-one-fire-out would hold out %s while training on %s, "
                    "which is the same complex (%s). This is the leak measured "
                    "in docs/leakfree_fold.md. Use leave_one_complex_out, or "
                    "pass on_complex_overlap='declare' with a written reason."
                    % (fire, ", ".join(siblings), held_cx))
            meta["complex_contaminated"] = True
            meta["complex_siblings_in_train"] = siblings
            meta["contamination_reason"] = reason.strip()
        splits.append(Split("leave_one_fire_out", k, fire, train, test, meta))
    return splits


def leave_one_complex_out(fire_ids: Sequence[str], *,
                          extra_complexes: Mapping[str, str] | None = None) -> list[Split]:
    """One fold per fire complex. The default for the roads direction.

    Every fire id must be registered. An unknown id is refused rather than
    treated as its own complex.
    """
    ids = _check_ids(fire_ids)
    cx = [complex_of(f, extra_complexes) for f in ids]
    order = sorted(set(cx))
    if len(order) < 2:
        raise LeakageRefusal(
            "leave-one-complex-out needs at least two complexes, found %r. "
            "With one complex there is no held-out set." % order)
    splits: list[Split] = []
    for k, c in enumerate(order):
        test = tuple(i for i, v in enumerate(cx) if v == c)
        train = tuple(i for i, v in enumerate(cx) if v != c)
        meta = {"complex": c,
                "fires_held_out": sorted({ids[i] for i in test}),
                "fires_in_train": sorted({ids[i] for i in train})}
        splits.append(Split("leave_one_complex_out", k, c, train, test, meta))
    return splits


# -------------------------------------------------------- spatial block CV --

class _Union:
    def __init__(self, keys: Iterable):
        self.parent = {k: k for k in keys}

    def find(self, a):
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _looks_like_degrees(xs: Sequence[float], ys: Sequence[float]) -> bool:
    """True when every coordinate falls in the Korean longitude and latitude box.

    Deliberately narrow. A wider test (anything inside plus or minus 180) fires
    on a small projected study area near a false origin, and a guard that fires
    on correct input is a guard that gets switched off.
    """
    return (all(120.0 <= x <= 135.0 for x in xs)
            and all(30.0 <= y <= 45.0 for y in ys))


def _grid_index(xs: Sequence[float], ys: Sequence[float],
                rows: Sequence[int], cell: float) -> dict:
    """Bucket ``rows`` into square cells of side ``cell`` for neighbour lookup."""
    index: dict[tuple[int, int], list[int]] = {}
    for j in rows:
        key = (int(math.floor(xs[j] / cell)), int(math.floor(ys[j] / cell)))
        index.setdefault(key, []).append(j)
    return index


def _has_neighbour(xs: Sequence[float], ys: Sequence[float], i: int,
                   index: dict, cell: float):
    """Index of a bucketed row within ``cell`` of row ``i``, or None."""
    cx, cy = int(math.floor(xs[i] / cell)), int(math.floor(ys[i] / cell))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for j in index.get((cx + dx, cy + dy), ()):
                if (xs[i] - xs[j]) ** 2 + (ys[i] - ys[j]) ** 2 < cell ** 2:
                    return j
    return None


def spatial_block_cv(xs: Sequence[float], ys: Sequence[float], *,
                     block_size_m: float,
                     n_folds: int = 5,
                     seed: int = 0,
                     buffer_m: float = 0.0,
                     fire_ids: Sequence[str] | None = None,
                     require_fire_disjoint: bool = False,
                     extra_complexes: Mapping[str, str] | None = None,
                     allow_degrees: bool = False) -> list[Split]:
    """Square-block spatial cross-validation in projected metres.

    Blocks are ``floor(x / block_size_m), floor(y / block_size_m)``. Blocks are
    grouped into ``n_folds`` folds, and a block never appears on both sides.

    ``buffer_m``
        Training rows within this distance of any test row are dropped, and the
        count lands in ``meta["dropped_to_buffer"]``. A block edge is not a
        barrier to spatial autocorrelation, so a block scheme without a buffer
        still trains on a row that is 10 m from a test row.

    ``require_fire_disjoint``
        With ``fire_ids`` given, blocks that share a fire are welded into one
        group before folds are assigned, so a fire never straddles a fold. Use
        this when units from several fires overlap in space.

    Degrees are refused unless ``allow_degrees`` is set. A block size of 5000
    in degrees is one block for the whole country, and it looks like it worked.
    """
    xs = [float(v) for v in xs]
    ys = [float(v) for v in ys]
    if len(xs) != len(ys):
        raise LeakageRefusal("xs and ys have different lengths, %d and %d" % (len(xs), len(ys)))
    if not xs:
        raise LeakageRefusal("no rows were given, so there is nothing to split")
    if any(not math.isfinite(v) for v in xs + ys):
        raise LeakageRefusal(
            "a coordinate is not finite. Missing coordinates must be resolved "
            "or the rows dropped before splitting, never imputed here.")
    if block_size_m <= 0:
        raise LeakageRefusal("block_size_m must be positive, got %r" % (block_size_m,))
    if n_folds < 2:
        raise LeakageRefusal("n_folds must be at least 2, got %r" % (n_folds,))
    if buffer_m < 0:
        raise LeakageRefusal("buffer_m must not be negative, got %r" % (buffer_m,))
    if not allow_degrees and _looks_like_degrees(xs, ys):
        raise LeakageRefusal(
            "these coordinates fall inside the Korean longitude and latitude "
            "box, so they look like degrees rather than projected metres. "
            "block_size_m is metres, so a block would span the whole country. "
            "Project to EPSG:5179 first, or pass allow_degrees=True and say in "
            "the pre-registration what unit block_size_m is in.")

    blocks = [(int(math.floor(x / block_size_m)), int(math.floor(y / block_size_m)))
              for x, y in zip(xs, ys)]
    uniq = sorted(set(blocks))

    group_of: dict[tuple[int, int], object] = {b: b for b in uniq}
    if require_fire_disjoint:
        if fire_ids is None:
            raise LeakageRefusal("require_fire_disjoint=True needs fire_ids")
        fids = _check_ids(fire_ids)
        if len(fids) != len(xs):
            raise LeakageRefusal(
                "fire_ids has %d entries and there are %d rows" % (len(fids), len(xs)))
        by_fire: dict[str, list[tuple[int, int]]] = {}
        for b, f in zip(blocks, fids):
            key = complex_of(f, extra_complexes, strict=False)
            by_fire.setdefault(key, []).append(b)
        uf = _Union(uniq)
        for bs in by_fire.values():
            first = bs[0]
            for b in bs[1:]:
                uf.union(first, b)
        group_of = {b: uf.find(b) for b in uniq}

    groups: dict[object, list[tuple[int, int]]] = {}
    for b in uniq:
        groups.setdefault(group_of[b], []).append(b)
    keys = sorted(groups, key=lambda g: (str(g),))
    if len(keys) < n_folds:
        raise LeakageRefusal(
            "%d spatial group(s) at block_size_m=%g cannot fill %d folds. Use a "
            "smaller block, fewer folds, or accept that the data does not "
            "support this many spatially independent folds."
            % (len(keys), block_size_m, n_folds))

    sizes: dict[object, int] = {g: 0 for g in keys}
    for b in blocks:
        sizes[group_of[b]] += 1
    rng = random.Random(seed)
    rng.shuffle(keys)
    keys.sort(key=lambda g: -sizes[g])          # stable, so seed breaks the ties
    assignment: dict[object, int] = {}
    load = [0] * n_folds
    for g in keys:
        f = min(range(n_folds), key=lambda i: (load[i], i))
        assignment[g] = f
        load[f] += sizes[g]

    fold_of_row = [assignment[group_of[b]] for b in blocks]
    splits: list[Split] = []
    for k in range(n_folds):
        test = tuple(i for i, f in enumerate(fold_of_row) if f == k)
        candidate = [i for i, f in enumerate(fold_of_row) if f != k]
        dropped = 0
        if buffer_m > 0 and test:
            index = _grid_index(xs, ys, test, buffer_m)
            keep = []
            for i in candidate:
                if _has_neighbour(xs, ys, i, index, buffer_m) is not None:
                    dropped += 1
                else:
                    keep.append(i)
            candidate = keep
        if not test:
            raise LeakageRefusal(
                "fold %d of spatial_block_cv is empty at block_size_m=%g; the "
                "block grid does not divide these rows" % (k, block_size_m))
        if not candidate:
            raise LeakageRefusal(
                "fold %d of spatial_block_cv has no training rows left after a "
                "buffer of %g m. Either the buffer is wider than the study "
                "area or the units are one contiguous patch." % (k, buffer_m))
        meta = {"block_size_m": block_size_m, "buffer_m": buffer_m, "seed": seed,
                "n_blocks_test": len({blocks[i] for i in test}),
                "n_blocks_total": len(uniq),
                "dropped_to_buffer": dropped,
                "require_fire_disjoint": bool(require_fire_disjoint)}
        splits.append(Split("spatial_block_cv", k, "block_fold_%d" % k,
                            tuple(candidate), test, meta))
    return splits


# ------------------------------------------------------- forward chaining --

def forward_chaining_by_year(years: Sequence[int], *,
                             min_train_years: int = 5,
                             horizon: int = 1,
                             gap_years: int = 0,
                             window_years: int | None = None) -> list[Split]:
    """Train on the past, test on the next ``horizon`` year(s).

    ``gap_years`` is an embargo between the last training year and the first
    test year. Use it whenever a feature looks back or forward across a year
    boundary, which in the suppression direction it does: a fire reported on
    31 December is contained in the next year.

    ``window_years`` turns the expanding window into a rolling one.
    """
    yrs = [int(y) for y in years]
    if not yrs:
        raise LeakageRefusal("no rows were given, so there is nothing to split")
    if horizon < 1:
        raise LeakageRefusal("horizon must be at least 1, got %r" % (horizon,))
    if gap_years < 0:
        raise LeakageRefusal("gap_years must not be negative, got %r" % (gap_years,))
    if min_train_years < 1:
        raise LeakageRefusal("min_train_years must be at least 1, got %r" % (min_train_years,))
    uniq = sorted(set(yrs))
    if len(uniq) < min_train_years + horizon:
        raise LeakageRefusal(
            "%d distinct year(s) cannot support min_train_years=%d plus a "
            "horizon of %d. Shorten the training requirement or say in the "
            "pre-registration that the record is too short for this scheme."
            % (len(uniq), min_train_years, horizon))

    splits: list[Split] = []
    fold = 0
    for i in range(min_train_years, len(uniq) - horizon + 1):
        test_years = uniq[i:i + horizon]
        cut = min(test_years) - 1 - gap_years
        train_years = [y for y in uniq[:i] if y <= cut]
        if window_years is not None:
            if window_years < 1:
                raise LeakageRefusal("window_years must be at least 1, got %r" % (window_years,))
            train_years = [y for y in train_years if y > cut - window_years]
        if len(train_years) < min_train_years:
            continue
        test = tuple(i2 for i2, y in enumerate(yrs) if y in set(test_years))
        train = tuple(i2 for i2, y in enumerate(yrs) if y in set(train_years))
        if not train or not test:
            continue
        meta = {"train_years": train_years, "test_years": test_years,
                "gap_years": gap_years, "window_years": window_years}
        splits.append(Split("forward_chaining_by_year", fold,
                            ",".join(str(y) for y in test_years), train, test, meta))
        fold += 1
    if not splits:
        raise LeakageRefusal(
            "forward chaining produced no usable fold. With %d distinct years, "
            "min_train_years=%d, horizon=%d and gap_years=%d there is no cut "
            "that leaves both sides non-empty."
            % (len(uniq), min_train_years, horizon, gap_years))
    return splits


# -------------------------------------------------------------- audits ----

def assert_group_disjoint(split: Split, groups: Sequence, label: str = "group") -> None:
    """Refuse if any group value appears on both sides of the fold.

    Run this on a hand-made split too. It is the one check that catches a split
    that was built somewhere other than this module.
    """
    if len(groups) <= max(list(split.train) + list(split.test)):
        raise LeakageRefusal(
            "groups has %d entries, which does not cover the indices in fold %d"
            % (len(groups), split.fold))
    tr = {groups[i] for i in split.train}
    te = {groups[i] for i in split.test}
    both = sorted(tr & te, key=str)
    if both:
        raise LeakageRefusal(
            "fold %d of %s has %s value(s) on both sides: %r"
            % (split.fold, split.scheme, label, both[:10]))


def assert_min_separation(split: Split, xs: Sequence[float], ys: Sequence[float],
                          min_m: float) -> None:
    """Refuse if a training row sits closer than ``min_m`` to a test row."""
    if min_m <= 0:
        return
    fx = [float(v) for v in xs]
    fy = [float(v) for v in ys]
    index = _grid_index(fx, fy, split.test, min_m)
    for i in split.train:
        j = _has_neighbour(fx, fy, i, index, min_m)
        if j is not None:
            d = math.sqrt((fx[i] - fx[j]) ** 2 + (fy[i] - fy[j]) ** 2)
            raise LeakageRefusal(
                "fold %d of %s has training row %d within %.1f m of test row "
                "%d, under a required separation of %g m"
                % (split.fold, split.scheme, i, d, j, min_m))


def assert_time_ordered(split: Split, years: Sequence[int], gap_years: int = 0) -> None:
    """Refuse if any training year is at or after the first test year."""
    tr = [int(years[i]) for i in split.train]
    te = [int(years[i]) for i in split.test]
    if not tr or not te:
        raise LeakageRefusal("fold %d has an empty side" % split.fold)
    cut = min(te) - gap_years
    offenders = sorted({y for y in tr if y >= cut})
    if offenders:
        raise LeakageRefusal(
            "fold %d of %s trains on year(s) %r which are not before the first "
            "test year %d with a gap of %d"
            % (split.fold, split.scheme, offenders, min(te), gap_years))


def audit_split(split: Split, *,
                fire_ids: Sequence[str] | None = None,
                extra_complexes: Mapping[str, str] | None = None,
                block_ids: Sequence | None = None,
                years: Sequence[int] | None = None,
                xs: Sequence[float] | None = None,
                ys: Sequence[float] | None = None,
                min_separation_m: float = 0.0,
                gap_years: int = 0,
                allow_complex_contamination: bool = False) -> None:
    """Run every applicable refusal against one fold.

    This is what A6 runs against a modeling agent's split before a number from
    it is looked at. Passing arguments that do not apply is fine; each check is
    skipped when its input is absent.
    """
    if fire_ids is not None:
        ids = [canonical_fire_id(f) for f in fire_ids]
        assert_group_disjoint(split, ids, "fire")
        cx = [complex_of(f, extra_complexes, strict=False) for f in ids]
        if not (allow_complex_contamination or split.meta.get("complex_contaminated")):
            assert_group_disjoint(split, cx, "complex")
    if block_ids is not None:
        assert_group_disjoint(split, list(block_ids), "spatial block")
    if years is not None:
        assert_time_ordered(split, years, gap_years)
    if xs is not None and ys is not None and min_separation_m > 0:
        assert_min_separation(split, xs, ys, min_separation_m)


# ----------------------------------------------------------- the registry --

#: The primary split per direction, fixed by A6 before any fit. A result quoted
#: under a different split is a secondary analysis and says so.
PRIMARY_SPLITS: dict[str, dict] = {
    "roads": {
        "scheme": "leave_one_complex_out",
        "kwargs": {},
        "minimum_units": 3,
        "why": ("five fires, and two of the candidate 2025 fires are one "
                "complex. The fire is the unit of independence, not the "
                "segment, because segments of one fire share a weather day."),
        "data_note": ("the effective sample size is the number of fires, not "
                      "the number of segments. Any interval computed by "
                      "resampling segments is too narrow."),
    },
    "landslides": {
        "scheme": "spatial_block_cv",
        "kwargs": {"block_size_m": 5000.0, "n_folds": 5, "buffer_m": 1000.0,
                   "seed": 20260916, "require_fire_disjoint": True},
        "minimum_units": 5,
        "why": ("slope units share storms, geology and a fire with their "
                "neighbours. Block size and buffer are pre-registered, with a "
                "declared sensitivity grid of 2000, 5000 and 10000 m."),
        "data_note": ("the landslide occurrence record on hand covers 2021 to "
                      "2025 and is address-level, so a spatial split does not "
                      "by itself make the unit assignment valid. See LEAKAGE.md "
                      "items C2 and C10 before using this scheme."),
    },
    "suppression": {
        "scheme": "forward_chaining_by_year",
        "kwargs": {"min_train_years": 10, "horizon": 1, "gap_years": 0},
        "minimum_units": 11,
        "why": ("the Korean record spans decades of changing doctrine and "
                "fleet, so a random split lets a later policy predict an "
                "earlier fire."),
        "data_note": ("the committed fire statistics extract covers 2022 to "
                      "2025 only, four distinct years, which this registered "
                      "scheme refuses. That refusal is correct and is the "
                      "point: the direction is conditional on the longer "
                      "record clearing WJ-001 and WJ-006. See LEAKAGE.md D5."),
    },
}


def primary_split_spec(direction: str) -> dict:
    """The pre-registered split for a direction. Unknown directions are refused."""
    key = str(direction).strip().lower()
    if key not in PRIMARY_SPLITS:
        raise LeakageRefusal(
            "no primary split is registered for direction %r. The registered "
            "directions are %s. A direction without a registered split does "
            "not get to invent one at fit time."
            % (direction, ", ".join(sorted(PRIMARY_SPLITS))))
    return dict(PRIMARY_SPLITS[key])
