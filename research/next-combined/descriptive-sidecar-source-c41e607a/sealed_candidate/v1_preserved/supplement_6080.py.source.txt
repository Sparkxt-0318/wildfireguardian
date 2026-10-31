"""Scratch candidate for CURRENT_DESCRIPTIVE_INTERVALS_V1, never model inference.

Actual execution requires exogenous root authorization and both independent
prerequisites. This scratch source is tested on invented data only and has no
actual execution authorization or completed independent candidate review.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import fcntl
import gzip
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import platform
import re
import sys
import types

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA256 = "5fd4314d7bfa7523fe3a19432c61198a93f8484abb83bc20a4ae7d11937088a0"
REVIEW_SHA256 = "b3f9513367f5666ca9f8ccde548db331c48251e7811f561ab8f2400ffe3d22cd"
REVIEW_RESULT_SHA256 = "3608188bd4167feadab082d3d970f251394f438bbffdf47865b47ad9e1650405"
BASELINES_SHA256 = "325abbe79ba7c22ed3eb60391a68d2becdbfd0aa4c6659debb94db6a34afbb1f"
PREREQUISITE_SHA256 = "b69a8b57ba8ddbb92cbfdd4e07195c82058be6051a42dbee38e262a873be62e0"
CENSUS_SHA256 = "8d29a5e1945c70581464d7262af399e4f485d131b33adc14a50b951696b8b9e9"
RESULT_CHECKER_SHA256 = "b3fb96f6c42a028b1e8ac67414b60e8b77735f9cf8559f784f546a7ab7929ee8"
ROOT_PROOF_SHA256 = "1e9def628deb2e7f1035aea691c39f8acf27f606bcdccffd0e6d3dff4f344db6"
FREEZE_COMMIT = "6887dc618253e6568c6cbbfd3c9a96f1d0d86b70"
INVENTORIES = {
    "us2024": ("research/forecast-v2/PREASSESSMENT_US2024_TIMESTAMPS.json", "51d910392b5f47f20b57ba56a4b2d25bc9096d33ac1dd09361f32a925884028d"),
    "korea2025": ("research/forecast-v2/PREASSESSMENT_KOREA2025_WINDOWS.json", "6286e0541a95b5f4806943bb809aa9314d55c2a637171002027c05e6292fc42d")}
FIGURES = tuple(f"fig{i:02d}_{name}" for i, name in enumerate(("reliability_all_models", "per_fire_brier_paired",
    "ablation_forest_plot", "meanfield_vs_mc_rmse_by_horizon", "example_forecast_vs_perimeter"), 1))
EXECUTION_STATUS = "REQUIRES_EXOGENOUS_ROOT_AUTHORIZATION_AND_ALL_PREREQUISITES"
ABSOLUTE = {"pooled_raw_brier": "brier", "pooled_average_precision": "average_precision",
            "pooled_roc_auc": "roc_auc", "pooled_ece_10_bins": "ece_10_bins",
            "pooled_clipped_nll": "clipped_nll"}
REFERENCES = ("persistence", "dilation_best")


class AdmissionError(ValueError):
    pass


def sha_bytes(blob):
    return hashlib.sha256(blob).hexdigest()


def object_sha(value):
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def array_sha(value):
    value = np.ascontiguousarray(value)
    return sha_bytes(str((value.shape, str(value.dtype))).encode() + value.tobytes())


def strict_json(blob):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AdmissionError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise AdmissionError(f"Nonfinite JSON constant: {value}")
    return json.loads(blob, object_pairs_hook=unique, parse_constant=invalid)


def protocol():
    blob = (HERE / "method/DESCRIPTIVE_INTERVAL_PROTOCOL_V1.json").read_bytes()
    if sha_bytes(blob) != PROTOCOL_SHA256:
        raise AdmissionError("The independently fixed descriptive protocol changed")
    for name, expected in (("REVIEW_SOURCE_INTERVALS.md", REVIEW_SHA256),
                           ("REVIEW_RESULT.json", REVIEW_RESULT_SHA256)):
        if sha_bytes((HERE / "method" / name).read_bytes()) != expected:
            raise AdmissionError("Inherited independent source review changed")
    return strict_json(blob)


def dependencies():
    actual = dict(numpy=np.__version__, sklearn=importlib.metadata.version("scikit-learn"),
                  scipy=importlib.metadata.version("scipy"), python=platform.python_version())
    if actual["numpy"] != "1.26.4" or actual["sklearn"] != "1.5.2" or actual["scipy"] != "1.13.1":
        raise AdmissionError("Exact fixed NumPy/SciPy/sklearn versions are required")
    return actual


_POINT_ENGINE = None


def frozen_point_engine():
    """Execute only exact frozen point-metric definitions, never data/model code."""
    global _POINT_ENGINE
    path = HERE / "frozen_source" / BASELINES_SHA256 / "baselines.py.gz"
    original = gzip.decompress(path.read_bytes())
    if sha_bytes(original) != BASELINES_SHA256:
        raise AdmissionError("Frozen point estimator source changed")
    if _POINT_ENGINE is None:
        tree = ast.parse(original)
        names = {"_average_precision", "_auc", "calibration_table", "score"}
        funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        constants = [node for node in tree.body if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id in {"LOG_FLOOR", "BINS"} for target in node.targets)]
        imports = [node for node in tree.body if isinstance(node, ast.Import)
                   and any(alias.name == "numpy" and alias.asname == "np" for alias in node.names)]
        nodes = imports + constants + funcs
        if {node.name for node in funcs} != names or len(constants) != 2 or len(imports) != 1:
            raise AdmissionError("Incomplete frozen point estimator closure")
        module = types.ModuleType("source_pinned_point_estimators")
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), module.__dict__)
        module.ast_identity = {str(i): sha_bytes(ast.dump(node, include_attributes=False).encode()) for i, node in enumerate(nodes)}
        _POINT_ENGINE = module
    return _POINT_ENGINE


@dataclass(frozen=True)
class Draws:
    matrix: np.ndarray
    multiplicities: np.ndarray
    vectors: np.ndarray
    inverse: np.ndarray
    frequencies: np.ndarray


def draw_plan(fire_order):
    """The literal fixed generator; no caller seed/draw-count option exists."""
    dependencies()
    count = len(fire_order)
    if count not in (4, 6) or len(set(fire_order)) != count:
        raise AdmissionError("Only the fixed complete four/six-fire cohort may be resampled")
    matrix = np.random.default_rng(20261030).integers(0, count, size=(10000, count))
    multiplicities = np.zeros((10000, count), dtype=np.int64)
    np.add.at(multiplicities, (np.repeat(np.arange(10000), count), matrix.ravel()), 1)
    vectors, inverse, frequencies = np.unique(multiplicities, axis=0, return_inverse=True, return_counts=True)
    if not np.array_equal(vectors[inverse], multiplicities) or int(frequencies.sum()) != 10000:
        raise AdmissionError("Multiplicity cache lost original draw frequencies")
    return Draws(matrix, multiplicities, vectors, inverse, frequencies)


def save_draws(path, draws):
    """Both NPY-container and exact little-endian int64 C-order payload identities."""
    path = Path(path)
    if path.exists():
        raise FileExistsError("Preserve earlier draw-matrix bytes")
    matrix = np.ascontiguousarray(draws.matrix, dtype="<i8")
    with path.open("xb") as stream:
        np.save(stream, matrix, allow_pickle=False)
    return dict(file=path.name, shape=list(matrix.shape), dtype=matrix.dtype.str, order="C",
                npy_sha256=sha_bytes(path.read_bytes()), little_endian_int64_payload_sha256=sha_bytes(matrix.tobytes(order="C")),
                multiplicity_vectors=len(draws.vectors), original_draws=10000,
                repeated_vector_frequencies_restored=True)


def checked_vectors(labels, predictions):
    if len(labels) != len(predictions) or len(labels) not in (4, 6):
        raise AdmissionError("Every expected fire needs the same complete model population")
    ys, ps = [], []
    for y, p in zip(labels, predictions):
        y, p = np.asarray(y), np.asarray(p)
        if (y.ndim != 1 or not len(y) or p.shape != y.shape or y.dtype.kind not in "biuf"
                or p.dtype.kind not in "iuf" or not np.isfinite(y).all() or not np.isin(y, (0, 1)).all()
                or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any()):
            raise AdmissionError("Nonempty binary labels and finite common-population probabilities in[0,1] are mandatory")
        ys.append(y.astype(np.float64)); ps.append(p.astype(np.float64))
    return ys, ps


def grouped_counts(labels, predictions):
    """Sparse exact score-group/fire counts; no probability rounding or tie splitting."""
    y = np.concatenate(labels)
    p = np.concatenate(predictions)
    fire = np.concatenate([np.full(len(a), f, dtype=np.int64) for f, a in enumerate(labels)])
    order = np.lexsort((fire, -p))
    scores, fi, truth = p[order], fire[order], y[order].astype(np.int64)
    score_start = np.r_[True, scores[1:] != scores[:-1]]
    group = np.cumsum(score_start) - 1
    pair_start = np.flatnonzero(score_start | np.r_[True, fi[1:] != fi[:-1]])
    return dict(groups=int(group[-1] + 1), group=group[pair_start], fire=fi[pair_start],
                counts=np.diff(np.r_[pair_start, len(y)]), positives=np.add.reduceat(truth, pair_start))


def ranking_values(groups, multiplicity):
    n = np.zeros(groups["groups"], dtype=np.int64)
    a = np.zeros_like(n)
    np.add.at(n, groups["group"], groups["counts"] * multiplicity[groups["fire"]])
    np.add.at(a, groups["group"], groups["positives"] * multiplicity[groups["fire"]])
    positives, negatives = int(a.sum()), int((n-a).sum())
    if not positives:
        return np.nan, np.nan
    use = n > 0
    seen, hit = np.cumsum(n), np.cumsum(a)
    ap = 1. if not negatives else float(np.sum((a[use] / positives) * (hit[use] / seen[use])))
    if not negatives:
        return ap, np.nan
    negative_groups = n-a
    below = negatives - np.cumsum(negative_groups)
    auc = float(np.sum(a.astype(np.float64) * (below + .5 * negative_groups)) / (positives * negatives))
    return ap, auc


def model_draw_values(labels, predictions, draws):
    labels, predictions = checked_vectors(labels, predictions)
    counts = np.array([len(y) for y in labels], dtype=np.int64)
    positives = np.array([int(y.sum()) for y in labels], dtype=np.int64)
    sse, loss, probability_bins, positive_bins = [], [], [], []
    bins = np.linspace(0., 1., 11)
    for y, p in zip(labels, predictions):
        index = np.clip(np.digitize(p, bins[1:-1], right=False), 0, 9)
        q = np.clip(p, 1e-7, 1-1e-7)
        sse.append(float(np.sum((p-y)**2)))
        loss.append(float(np.sum(-(y*np.log(q)+(1-y)*np.log1p(-q)))))
        probability_bins.append(np.bincount(index, weights=p, minlength=10))
        positive_bins.append(np.bincount(index, weights=y, minlength=10))
    m = draws.vectors
    denominator = m @ counts
    groups = grouped_counts(labels, predictions)
    ranking = np.array([ranking_values(groups, row) for row in m])
    unique = dict(pooled_raw_brier=(m @ np.array(sse))/denominator,
                  pooled_average_precision=ranking[:, 0], pooled_roc_auc=ranking[:, 1],
                  pooled_ece_10_bins=np.abs(m @ (np.array(probability_bins)-np.array(positive_bins))).sum(1)/denominator,
                  pooled_clipped_nll=(m @ np.array(loss))/denominator)
    values = {name: a[draws.inverse] for name, a in unique.items()}
    no_positive = (draws.multiplicities @ positives) == 0
    no_negative = (draws.multiplicities @ (counts-positives)) == 0
    raw = frozen_point_engine().score(np.concatenate(labels), np.concatenate(predictions))
    point = {field: None if raw[name] is None else float(raw[name]) for field, name in ABSOLUTE.items()}
    return point, values, no_positive, no_negative


def interval(values, point, no_positive, no_negative, *, kind):
    values = np.asarray(values, dtype=np.float64)
    if values.shape != (10000,):
        raise AdmissionError("Every original bootstrap draw must be preserved")
    undefined_positive = no_positive if kind in ("ap", "paired_ap", "auc") else np.zeros(10000, bool)
    undefined_negative = no_negative if kind == "auc" else np.zeros(10000, bool)
    undefined = undefined_positive | undefined_negative
    if not np.array_equal(~np.isfinite(values), undefined):
        raise AdmissionError("Undefined metric draws disagree with the fixed absent-class policy")
    defined = values[~undefined]
    conditional = np.quantile(defined, [.025, .975], method="linear").tolist() if len(defined) else None
    full = conditional if point is not None and not undefined.any() else None
    return dict(point=point, percentile_95_interval=full,
        status="AVAILABLE_FULL_95_INTERVAL" if full is not None else "UNAVAILABLE_UNDEFINED_POINT_OR_DRAW",
        draws=10000, seed=20261030, defined_draws=int((~undefined).sum()),
        undefined_no_positive_draws=int(undefined_positive.sum()), undefined_no_negative_draws=int(undefined_negative.sum()),
        undefined_union_draws=int(undefined.sum()),
        conditional_on_defined_draws_interval=conditional,
        conditional_scope=("conditional on a draw containing both classes" if kind == "auc" else
                           "conditional on a draw containing positive labels" if kind in ("ap", "paired_ap") else
                           "all validated nonempty draws"),
        quantile_method="linear", interval_unit="whole fire, pooled canonical cell-interval entries")


def compute_cohort(cohort, labels, model_loader, canonical_points):
    """Internal estimator, callable only after the separate custody layer passes.

    This API does not authenticate root execution permission or certify actual
    study admission. The CLI additionally requires all authenticated receipts.
    """
    method = protocol()
    order = method["cohorts"][cohort]["fire_order"]
    if order != sorted(order):
        raise AdmissionError("Fixed fire order must match the frozen canonical sorted-file concatenation")
    if len(labels) != len(order) or set(canonical_points) != set(method["model_order"]):
        raise AdmissionError("The complete fixed cohort and all16 fixed model points are required")
    draws = draw_plan(order)
    results, ap_values, ap_points = {}, {}, {}
    counts_positive = counts_negative = None
    for name in method["model_order"]:
        point, values, no_positive, no_negative = model_draw_values(labels, model_loader(name), draws)
        expected = canonical_points[name]
        if (set(expected) != set(ABSOLUTE.values())
                or any((expected[key] is not None and (type(expected[key]) not in (int, float) or not math.isfinite(expected[key])))
                       or point[field] != expected[key] for field, key in ABSOLUTE.items())):
            raise AdmissionError("Supplement raw original points differ from canonical raw fields")
        results[name] = {field: interval(values[field], point[field], no_positive, no_negative,
            kind="ap" if field == "pooled_average_precision" else "auc" if field == "pooled_roc_auc" else "finite")
            for field in ABSOLUTE}
        ap_values[name], ap_points[name] = values["pooled_average_precision"], point["pooled_average_precision"]
        counts_positive, counts_negative = no_positive, no_negative
    paired = {}
    for name in method["model_order"]:
        for reference in REFERENCES:
            point = None if ap_points[name] is None else ap_points[name]-ap_points[reference]
            record = interval(ap_values[name]-ap_values[reference], point, counts_positive, counts_negative, kind="paired_ap")
            record.update(candidate=name, reference=reference, estimand="pooled AP(candidate) minus pooled AP(reference)",
                          favourable_direction="positive", descriptive_secondary_only=True)
            paired[f"{name}__vs__{reference}"] = record
    return dict(cohort=cohort, fire_order=order, model_order=method["model_order"],
        fire_count=len(order), entry_count=sum(len(y) for y in labels), models=results, paired_ap=paired,
        protocol_sha256=PROTOCOL_SHA256, execution_status="INTERNAL_ESTIMATOR_RESULT_NO_EXECUTION_AUTHORITY",
        frozen_primary_unchanged=True, promotion_criteria_pass=False,
        interpretation=method["interpretation"]), draws


@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str


@dataclass(frozen=True)
class ExpectedCase:
    case_id: str
    identity: dict
    source_fields: dict
    receipt: Artifact
    entries: Artifact | None
    rows_sha256: str | None
    cols_sha256: str | None
    labels_sha256: str | None
    mask_sha256: str
    cells: int
    positives: int | None


@dataclass(frozen=True)
class CohortExpectation:
    cohort: str
    directory: Path
    assessment: Artifact
    frozen: Artifact
    canonical_report: Artifact
    cases: tuple[ExpectedCase, ...]
    per_fire: dict[str, Artifact]
    source_artifacts: tuple[Artifact, ...]
    input_artifacts: tuple[Artifact, ...]
    prerequisite_artifacts: tuple[Artifact, ...]
    expected_source_map_sha256: str
    expected_input_map_sha256: str
    expected_prerequisite_map_sha256: str


class Files:
    def __init__(self):
        self.seen = {}

    def read(self, artifact):
        path = Path(artifact.path)
        if not path.is_absolute() or any(part.is_symlink() for part in (path, *path.parents)):
            raise AdmissionError("Pinned artifact must be an explicit regular nonsymlink path")
        if not path.is_file():
            raise AdmissionError("Missing required canonical artifact")
        data = path.read_bytes()
        if sha_bytes(data) != artifact.sha256:
            raise AdmissionError("Canonical consumed artifact bytes changed")
        if str(path) in self.seen and self.seen[str(path)] != artifact.sha256:
            raise AdmissionError("One canonical path has conflicting identities")
        self.seen[str(path)] = artifact.sha256
        return data

    def json(self, artifact):
        return strict_json(self.read(artifact))

    def npz(self, artifact):
        return np.load(io.BytesIO(self.read(artifact)), allow_pickle=False)

    def unchanged(self):
        for path, expected in self.seen.items():
            self.read(Artifact(Path(path), expected))
        return dict(self.seen)


SOURCE_FIELDS = {"initial_sha256", "endpoint_sha256", "environmental_snapshot_sha256",
    "reference_mask_sha256", "initial_age_sha256", "residence_sha256", "rectangle", "reference_cells", "weather_hour"}


def identity_map(artifacts):
    result = {}
    for artifact in artifacts:
        key = str(artifact.path)
        if key in result:
            raise AdmissionError("Duplicate artifact in sealed custody expectation")
        result[key] = artifact.sha256
    return result


def check_bindings(files, expected):
    for artifacts, digest in ((expected.source_artifacts, expected.expected_source_map_sha256),
                              (expected.input_artifacts, expected.expected_input_map_sha256),
                              (expected.prerequisite_artifacts, expected.expected_prerequisite_map_sha256)):
        mapping = identity_map(artifacts)
        if not mapping or object_sha(mapping) != digest:
            raise AdmissionError("Missing/extra source, input or independent-review binding")
        for artifact in artifacts:
            files.read(artifact)


def checked_case(files, expected, record, frozen_sha, models):
    if (record.get("receipt_version") != "wfg.forecast-assessment-case/2"
            or record.get("case_id") != expected.case_id or record.get("case") != expected.identity
            or record.get("assessment_sha256") != frozen_sha
            or set(expected.source_fields) != SOURCE_FIELDS
            or any(record.get(name) != value for name, value in expected.source_fields.items())
            or files.json(expected.receipt) != record):
        raise AdmissionError("Individual case, source identity or frozen receipt mismatch")
    if record.get("status") != "SCORED":
        if record.get("status") not in ("UNAVAILABLE", "FAILED") or not record.get("reason") or expected.entries is not None:
            raise AdmissionError("Unavailable canonical case requires its original outcome/reason and no prediction")
        return None
    if expected.entries is None or record.get("sha256") != expected.entries.sha256:
        raise AdmissionError("Missing exact individual prediction binding")
    with files.npz(expected.entries) as data:
        if set(data.files) != {"row", "col", "y", *("p_"+name for name in models)}:
            raise AdmissionError("Every case must contain all and only the16 fixed probability columns")
        row, col, y = data["row"], data["col"], data["y"]
        shape = expected.source_fields["rectangle"]
        if (not isinstance(shape, list) or len(shape) != 2 or any(type(n) is not int or n <= 0 for n in shape)
                or row.dtype.kind not in "iu" or col.dtype.kind not in "iu" or row.ndim != 1 or col.shape != row.shape
                or y.shape != row.shape or not len(y) or not np.isin(y, (0, 1)).all()
                or (row < 0).any() or (col < 0).any() or (row >= shape[0]).any() or (col >= shape[1]).any()
                or (np.diff(row.astype(np.int64)*shape[1] + col.astype(np.int64)) <= 0).any()):
            raise AdmissionError("Case coordinates must be complete ordered integer source cells with binary labels")
        mask = np.zeros(shape, bool); mask[row, col] = True
        if (array_sha(row) != expected.rows_sha256 or array_sha(col) != expected.cols_sha256
                or array_sha(y) != expected.labels_sha256 or array_sha(mask) != expected.mask_sha256
                or record.get("scored_mask_sha256") != expected.mask_sha256
                or type(expected.cells) is not int or expected.cells <= 0 or len(y) != expected.cells
                or record.get("scored_cells") != expected.cells or int(y.sum()) != expected.positives
                or record.get("positives") != expected.positives
                or record.get("scored_cells", 0) + record.get("excluded_cells", -1) != record.get("reference_cells")):
            raise AdmissionError("Full expected support, ordered labels or case counts changed")
        for name in models:
            p = data["p_"+name]
            if p.dtype.kind not in "iuf" or p.shape != y.shape or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
                raise AdmissionError("Invalid common-population probability cannot become an exclusion")
        return dict(row=row.copy(), col=col.copy(), y=y.copy())


@dataclass
class CanonicalCohort:
    expected: CohortExpectation
    files: Files
    labels: list[np.ndarray]
    points: dict
    per_fire_counts: list[int]

    def model(self, name):
        if name not in protocol()["model_order"]:
            raise AdmissionError("Caller-selected model cannot enter the fixed cohort")
        values = []
        for event in protocol()["cohorts"][self.expected.cohort]["fire_order"]:
            with self.files.npz(self.expected.per_fire[event]) as aggregate:
                values.append(aggregate["p_"+name].astype(np.float64))
        return values

    def after(self):
        return self.files.unchanged()


def verify_cohort(expected):
    """Strict inner join against sealed expectations; no available-fire fallback.

    Returns a null-cohort descriptor for honest unavailable canonical support.
    Missing/corrupt/unlisted data raise AdmissionError. Root prerequisite receipt
    authentication is handled by the separate outer boundary.
    """
    method = protocol()
    if expected.cohort not in method["cohorts"]:
        raise AdmissionError("Unknown cohort")
    spec = method["cohorts"][expected.cohort]
    models = method["model_order"]
    files = Files(); check_bindings(files, expected)
    assessment, frozen, report = files.json(expected.assessment), files.json(expected.frozen), files.json(expected.canonical_report)
    records = assessment.get("cases", [])
    ids = [case.case_id for case in expected.cases]
    if (len(expected.cases) != spec["expected_cases"] or len(set(ids)) != len(ids)
            or [record.get("case_id") for record in records] != ids
            or assessment.get("receipt_version") != "wfg.forecast-assessment/2"
            or assessment.get("frozen_sha256") != expected.frozen.sha256
            or set(assessment.get("events", [])) != set(spec["fire_order"])
            or len(assessment.get("events", [])) != len(spec["fire_order"])
            or frozen.get("cohort") != expected.cohort
            or report.get("model_selection_sha256") != frozen.get("selection_sha256")
            or not frozen.get("selection_sha256") or report.get("current_phase") != frozen.get("current_phase")):
        raise AdmissionError("Complete fixed case/fire population or canonical frozen source/selection differs")
    report_key = "heldout" if expected.cohort == "us2024" else "korean2025_secondary_reconstruction"
    canonical = report.get(report_key, {})
    if canonical.get("assessment_status") != assessment.get("status"):
        raise AdmissionError("Canonical report and assessment status differ")
    directory = Path(expected.directory)
    actual_case_json = {p.resolve() for p in (directory/"cases").glob("*.json")}
    if actual_case_json != {Path(case.receipt.path).resolve() for case in expected.cases}:
        raise AdmissionError("Missing/extra canonical case receipts")
    actual_case_npz = {p.resolve() for p in (directory/"cases").glob("*.npz")}
    if actual_case_npz != {Path(case.entries.path).resolve() for case in expected.cases if case.entries is not None}:
        raise AdmissionError("Missing/extra canonical case predictions")
    blocks, outcomes = {}, []
    for wanted, record in zip(expected.cases, records):
        identity = wanted.identity
        import json
        cid = sha_bytes(json.dumps(identity, sort_keys=True).encode())[:24]
        if cid != wanted.case_id or set(identity) != {"event", "cutoff", "endpoint", "hours"} or identity["event"] not in spec["fire_order"]:
            raise AdmissionError("Case membership/identity differs from sealed complete inventory")
        arrays = checked_case(files, wanted, record, expected.frozen.sha256, models)
        blocks.setdefault(identity["event"], []).append((wanted, record, arrays))
        if arrays is None:
            outcomes.append(record)
    if set(blocks) != set(spec["fire_order"]):
        raise AdmissionError("Every fixed fire must have its expected nonempty case inventory")
    if assessment.get("status") != "COMPLETE" or outcomes or assessment.get("failed_or_unavailable"):
        if assessment.get("status") != "HOLD" or not assessment.get("failed_or_unavailable"):
            raise AdmissionError("Incomplete canonical support must remain an explicit HOLD with original reasons")
        return dict(cohort=expected.cohort, status="UNAVAILABLE_COMPLETE_CANONICAL_SUPPORT", complete_cohort=False,
                    metrics=None, original_outcomes=assessment["failed_or_unavailable"], promotion_criteria_pass=False,
                    artifact_hashes=files.unchanged(), execution_status=EXECUTION_STATUS)
    if (set(expected.per_fire) != set(spec["fire_order"])
            or assessment.get("per_fire_files") != {Path(pin.path).name: pin.sha256 for pin in expected.per_fire.values()}
            or {p.resolve() for p in directory.glob("*.npz")} != {Path(pin.path).resolve() for pin in expected.per_fire.values()}
            or set(canonical.get("models", {})) != set(models)):
        raise AdmissionError("All16 fixed models and exact complete per-fire aggregates are required")
    labels, totals = [], []
    for event in spec["fire_order"]:
        pieces = blocks[event]
        with files.npz(expected.per_fire[event]) as aggregate:
            if set(aggregate.files) != {"interval", "row", "col", "y", "t1", "hours", *("p_"+name for name in models)}:
                raise AdmissionError("Per-fire canonical aggregate schema changed")
            y = np.concatenate([arrays["y"] for _, _, arrays in pieces])
            counts = [len(arrays["y"]) for _, _, arrays in pieces]
            if (aggregate["y"].dtype != y.dtype or not np.array_equal(aggregate["y"], y)
                    or not np.array_equal(aggregate["interval"], np.repeat(np.arange(len(pieces)), counts))
                    or aggregate["interval"].dtype.kind not in "iu"
                    or aggregate["t1"].tolist() != [case.identity["cutoff"] for case, _, _ in pieces]
                    or aggregate["hours"].tolist() != [case.identity["hours"] for case, _, _ in pieces]):
                raise AdmissionError("Canonical interval membership, order or labels changed")
            for key in ("row", "col"):
                wanted = np.concatenate([arrays[key] for _, _, arrays in pieces])
                if aggregate[key].dtype != wanted.dtype or not np.array_equal(aggregate[key], wanted):
                    raise AdmissionError("Per-fire coordinates differ from every canonical case")
            bounds = np.r_[0, np.cumsum(counts)]
            for name in models:
                p = aggregate["p_"+name]
                if p.shape != y.shape or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
                    raise AdmissionError("Invalid complete per-fire model probability")
                for index, (case, _, _) in enumerate(pieces):
                    with files.npz(case.entries) as individual:
                        value = individual["p_"+name]
                        if p.dtype != value.dtype or not np.array_equal(p[bounds[index]:bounds[index+1]], value):
                            raise AdmissionError("Individual/per-fire probabilities disagree")
            labels.append(y.astype(np.float64)); totals.append(len(y))
    if any(not set(ABSOLUTE.values()).issubset(canonical["models"][name]["pooled"]) for name in models):
        raise AdmissionError("Canonical original point fields cannot be missing or inferred null")
    points = {name: {key: canonical["models"][name]["pooled"][key] for key in ABSOLUTE.values()} for name in models}
    files.unchanged()
    return CanonicalCohort(expected, files, labels, points, totals)


def verify_both(expectations):
    if set(expectations) != {"us2024", "korea2025"}:
        raise AdmissionError("Both fixed cohorts must remain separately represented")
    results = {}
    for cohort in ("us2024", "korea2025"):
        try:
            results[cohort] = verify_cohort(expectations[cohort])
        except (AdmissionError, FileNotFoundError, KeyError, ValueError, TypeError) as error:
            results[cohort] = dict(cohort=cohort, status="UNAVAILABLE_ADMISSION_FAILURE", metrics=None,
                complete_cohort=False, reason=str(error), promotion_criteria_pass=False, execution_status=EXECUTION_STATUS)
    return results


def same(actual, expected, message):
    if object_sha(actual) != object_sha(expected):
        raise AdmissionError(message)


def digest_string(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def relative_path(root, value):
    if (type(value) is not str or not value or "\\" in value or Path(value).is_absolute()
            or str(Path(value)) != value or any(part in (".", "..") for part in value.split("/"))):
        raise AdmissionError("Evidence path must be normalized repository-relative")
    path = root/value
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.resolve().is_relative_to(root):
        raise AdmissionError("Symlink or path escape in evidence")
    return path


def artifact_pointer(root, value):
    if not isinstance(value, dict) or set(value) != {"path", "sha256"} or not digest_string(value["sha256"]):
        raise AdmissionError("Identity must contain exactly normalized path and exact SHA256")
    return Artifact(relative_path(root, value["path"]), value["sha256"])


def fixed_prerequisites():
    path = HERE/"method/DESCRIPTIVE_INTERVAL_PREREQUISITES_V1.json"
    blob = path.read_bytes()
    if sha_bytes(blob) != PREREQUISITE_SHA256:
        raise AdmissionError("Root prerequisite specification changed")
    return strict_json(blob)


def checked_map(root, mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise AdmissionError("A nonempty complete artifact map is mandatory")
    return {name: artifact_pointer(root, dict(path=name, sha256=digest)) for name, digest in mapping.items()}


@dataclass
class Authorized:
    root: Path
    run: Path
    out: Path
    authorization: dict
    authorization_sha256: str
    files: Files
    inputs: dict[str, Artifact]
    frozen: dict[str, Artifact]
    bindings: dict
    census: dict
    review: dict
    report: dict
    assessments: dict
    frozen_assessments: dict

    def input(self, relative):
        if relative not in self.inputs:
            raise AdmissionError("Unlisted consumed canonical artifact: " + relative)
        return self.inputs[relative]


def authorize(root, run, results, out, authorization_path, expected_authorization_sha256):
    """Root hash is exogenous. No receipt can provide its own expected digest."""
    if not digest_string(expected_authorization_sha256):
        raise AdmissionError("An independently supplied root authorization SHA256 is mandatory")
    root = Path(root)
    if not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
        raise AdmissionError("Explicit nonsymlink absolute model root required")
    root = root.resolve()
    files = Files()
    # Only the authorization itself is opened before its external root hash passes.
    auth_pin = Artifact(Path(authorization_path).absolute(), expected_authorization_sha256)
    auth = files.json(auth_pin)
    spec = fixed_prerequisites(); method = protocol()
    required = set(spec["root_actual_authorization"]["required_fields"])
    if not isinstance(auth, dict) or set(auth) != required:
        raise AdmissionError("Root authorization fields are incomplete or extra")
    same(auth["receipt_version"], "wfg.current-descriptive-interval-authorization/1", "Wrong root authorization schema")
    same(auth["status"], "AUTHORIZED_SAVED_OUTPUT_ONLY", "No root saved-output execution authorization")
    for key, value in spec["root_actual_authorization"]["fixed_values"].items():
        same(auth[key], value, "Root authorization changed fixed " + key)
    same(auth["prerequisite_spec_sha256"], PREREQUISITE_SHA256, "Wrong prerequisite spec")
    same(auth["model_order"], method["model_order"], "Exact16 model order is mandatory")
    if auth["model_root"] != str(root) or not re.fullmatch(r"[0-9a-f]{40}", str(auth["canonical_review_source_head"])):
        raise AdmissionError("Root/source-head identity differs")
    try:
        issued = datetime.fromisoformat(auth["issued_utc"])
        if issued.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError):
        raise AdmissionError("Root authorization needs a timezone-bound issued_utc")
    canonical_run = relative_path(root, auth["run_relative_path"])
    canonical_out = relative_path(root, auth["output_relative_directory"])
    if (Path(run).resolve() != canonical_run or Path(out).resolve() != canonical_out
            or not auth["output_relative_directory"].startswith("research/forecast-v2/supplements/")
            or canonical_out.exists()):
        raise AdmissionError("Exact new separate output directory and run are mandatory")
    source = artifact_pointer(root, auth["supplement_source"])
    if source.path != Path(__file__).resolve():
        raise AdmissionError("Actually executing supplement source differs from authorized source")
    files.read(source)
    source_review = artifact_pointer(root, auth["independent_source_review"])
    files.read(source_review)  # Root binds exact review bytes, not a caller Boolean.
    inputs = checked_map(root, auth["input_artifacts_sha256"])
    frozen = checked_map(root, auth["frozen_files_sha256"])
    if len(frozen) != 223:
        raise AdmissionError("The exact complete223-file root freeze is required")
    proof_names = [name for name, pin in inputs.items() if Path(name).name == "FREEZE_PARENT_VERIFICATION.json" and pin.sha256 == ROOT_PROOF_SHA256]
    if len(proof_names) != 1:
        raise AdmissionError("The independently hard-pinned root freeze proof is missing or duplicated")
    proof = files.json(inputs[proof_names[0]])
    same(proof.get("verified_file_sha256"), auth["frozen_files_sha256"], "Root223 proof/map disagreement")
    for pin in frozen.values():
        files.read(pin)
    # Hash every authorized consumed artifact before any scientific NPZ load.
    for name, pin in inputs.items():
        if pin.path.suffix in {".pt", ".pkl"}:
            raise AdmissionError("Model binaries are not consumed by this saved-output supplement")
        files.read(pin)
    def consume(value):
        pin = artifact_pointer(root, value)
        relative = str(pin.path.relative_to(root))
        if relative not in inputs or inputs[relative] != pin:
            raise AdmissionError("Consumed artifact missing from exact authorized input map")
        return pin
    # Method, spec, inherited review and exact point AST source are consumed too.
    for path in (HERE/"method/DESCRIPTIVE_INTERVAL_PROTOCOL_V1.json", HERE/"method/DESCRIPTIVE_INTERVAL_PREREQUISITES_V1.json",
                 HERE/"method/REVIEW_SOURCE_INTERVALS.md", HERE/"method/REVIEW_RESULT.json",
                 HERE/"frozen_source"/BASELINES_SHA256/"baselines.py.gz", source_review.path, source.path):
        if not path.is_relative_to(root):
            raise AdmissionError("Trusted method/source copies must be bundled inside authorized root")
        relative = str(path.relative_to(root))
        if relative not in inputs:
            raise AdmissionError("Unlisted method/review/source artifact")
    checks = auth["checker_sources"]
    if not isinstance(checks, dict) or set(checks) != {"census", "canonical_result"}:
        raise AdmissionError("Both exact immutable checker sources are required")
    for key, expected in (("census", CENSUS_SHA256), ("canonical_result", RESULT_CHECKER_SHA256)):
        if consume(checks[key]).sha256 != expected:
            raise AdmissionError("Unreviewed independent checker source")
    bindings = auth["canonical_bindings"]
    if not isinstance(bindings, dict) or set(bindings) != {"results", "selection", "registry", "assessments", "frozen_assessments", "figures"}:
        raise AdmissionError("Complete canonical bindings required")
    for key in ("results", "selection", "registry"):
        consume(bindings[key])
    if Path(results).resolve() != consume(bindings["results"]).path:
        raise AdmissionError("Results argument differs from authorized canonical report")
    for key in ("assessments", "frozen_assessments"):
        if set(bindings[key]) != {"us2024", "korea2025"}:
            raise AdmissionError("Both cohort bindings required")
        for value in bindings[key].values():
            consume(value)
    if set(bindings["figures"]) != set(FIGURES):
        raise AdmissionError("All five canonical PNG/SVG figure pairs are required")
    for pair in bindings["figures"].values():
        if set(pair) != {"png", "svg"}:
            raise AdmissionError("Each figure requires both formats")
        for value in pair.values():
            consume(value)
    prerequisites = auth["prerequisite_receipts"]
    if not isinstance(prerequisites, dict) or set(prerequisites) != {"census", "canonical_result"}:
        raise AdmissionError("Both independent prerequisite receipts required")
    census = files.json(consume(prerequisites["census"]))
    review = files.json(consume(prerequisites["canonical_result"]))
    for key, value in spec["census_receipt"]["required_fields"].items():
        same(census.get(key), value, "Census prerequisite field changed: " + key)
    for key, value in spec["canonical_result_review"]["required_fields"].items():
        same(review.get(key), value, "Canonical result prerequisite field changed: " + key)
    same(review.get("authorized_source_head"), auth["canonical_review_source_head"], "Canonical review head differs")
    for key, field in (("results", "results_sha256"), ("selection", "selection_sha256"), ("registry", "registry_sha256")):
        same(review.get(field), bindings[key]["sha256"], "Canonical review binding changed: " + field)
    same(census.get("assessment_sha256"), {key: value["sha256"] for key, value in bindings["assessments"].items()}, "Census assessment hashes changed")
    reported = files.json(consume(bindings["results"]))
    for stem, pair in bindings["figures"].items():
        for extension, value in pair.items():
            pin = consume(value)
            if pin.path != Path(results).resolve().parent/"figures"/(stem+"."+extension):
                raise AdmissionError("Canonical figure identity path changed")
            same(value["sha256"], reported["figure_evidence"][stem]["files_sha256"][extension], "Canonical figure/report hash differs")
    for cohort, folder in (("us2024", "heldout"), ("korea2025", "korean2025")):
        for key, filename in (("assessments", "ASSESSMENT.json"), ("frozen_assessments", "FROZEN_ASSESSMENT.json")):
            if consume(bindings[key][cohort]).path != canonical_run/folder/filename:
                raise AdmissionError("Canonical cohort receipt path changed")
    assessments = {key: files.json(consume(value)) for key, value in bindings["assessments"].items()}
    frozen_assessments = {key: files.json(consume(value)) for key, value in bindings["frozen_assessments"].items()}
    expected_arrays = set()
    for cohort, folder in (("us2024", "heldout"), ("korea2025", "korean2025")):
        directory = canonical_run/folder
        expected_arrays.update(str((directory/name).relative_to(root)) for name in assessments[cohort]["per_fire_files"])
        expected_arrays.update(str((directory/"cases"/(r["case_id"]+".npz")).relative_to(root))
                               for r in assessments[cohort]["cases"] if r["status"] == "SCORED")
    if {name for name in inputs if Path(name).suffix in {".npz", ".npy"}} != expected_arrays:
        raise AdmissionError("Input map has missing/extra scientific array artifacts")
    protected = [*files.seen, str(source.path), str(auth_pin.path)]
    if any(canonical_out == Path(path) or Path(path).is_relative_to(canonical_out) or canonical_out.is_relative_to(Path(path)) for path in protected):
        raise AdmissionError("Separate output overlaps protected input/source/canonical evidence")
    return Authorized(root, canonical_run, canonical_out, auth, expected_authorization_sha256, files, inputs, frozen,
                      bindings, census, review, reported, assessments, frozen_assessments)


def cohort_expectation(authorized, cohort, *, metadata_only=False):
    """Reconcile exact frozen inventory and all checker child keys before arrays."""
    a = authorized
    method = protocol(); spec = method["cohorts"][cohort]
    assessment = a.assessments[cohort]
    inventory_path, inventory_sha = INVENTORIES[cohort]
    inventory_pin = a.input(inventory_path)
    if inventory_pin.sha256 != inventory_sha:
        raise AdmissionError("Frozen case inventory differs from the prescribed hard pin")
    inventory = a.files.json(inventory_pin)
    originals = inventory["cases"] if cohort == "us2024" else [r["case"] for r in inventory["cases"]]
    def cid(case):
        return sha_bytes(json.dumps(case, sort_keys=True, allow_nan=False).encode())[:24]
    expected_ids = [cid(case) for case in originals]
    expected = dict(zip(expected_ids, originals))
    records = assessment["cases"]
    actual_ids = [r["case_id"] for r in records]
    if (inventory.get("case_count") != spec["expected_cases"] or len(expected_ids) != spec["expected_cases"]
            or len(expected) != spec["expected_cases"] or set(actual_ids) != set(expected_ids)
            or len(actual_ids) != len(set(actual_ids)) or len(actual_ids) != spec["expected_cases"]
            or set(case["event"] for case in originals) != set(spec["fire_order"])):
        raise AdmissionError("Missing/extra/corrupt complete frozen case population")
    if cohort == "korea2025":
        same([row["case_id"] for row in inventory["cases"]], expected_ids, "Frozen Korean case IDs changed")
        same(inventory["case_ids"], expected_ids, "Frozen Korean case list changed")
    for record in records:
        same(record["case"], expected[record["case_id"]], "Frozen case identity changed")
        if record["status"] not in ("SCORED", "UNAVAILABLE", "FAILED"):
            raise AdmissionError("Unknown case outcome")
        if record.get("receipt_version") != "wfg.forecast-assessment-case/2" or record.get("assessment_sha256") != a.bindings["frozen_assessments"][cohort]["sha256"]:
            raise AdmissionError("Individual case frozen receipt identity changed")
    statuses = dict(Counter(r["status"] for r in records))
    outcomes = [r for r in records if r["status"] != "SCORED"]
    same(assessment.get("failed_or_unavailable"), outcomes, "Original unavailable/failed outcomes or reasons changed")
    if assessment["status"] not in ("COMPLETE", "HOLD") or (assessment["status"] == "COMPLETE" and outcomes):
        raise AdmissionError("Complete status cannot suppress unavailable case outcomes")
    report_key = "heldout" if cohort == "us2024" else "korean2025_secondary_reconstruction"
    same(a.report[report_key].get("assessment_status"), assessment["status"], "Canonical report/assessment status differs")
    events = list(dict.fromkeys(case["event"] for case in originals))
    child = dict(status="COMPLETE_FROZEN_CASE_CENSUS", cohort=cohort, expected_cases=len(originals), represented_cases=len(records),
        unique_cases=len(set(actual_ids)), expected_fires=len(events), per_fire_counts=dict(Counter(case["event"] for case in originals)),
        outcome_counts=statuses, assessment_status=assessment["status"], case_order_matches_inventory=actual_ids == expected_ids,
        declared_event_order_matches_inventory=assessment["events"] == events,
        case_population_sha256=sha_bytes(json.dumps(sorted(actual_ids), separators=(",", ":")).encode()),
        inventory_path=inventory_path, inventory_sha256=inventory_sha)
    same(a.census["cohorts"][cohort], child, "Census child keys/population no longer match canonical assessment")
    folder = "heldout" if cohort == "us2024" else "korean2025"
    directory = a.run/folder
    same(assessment.get("frozen_sha256"), a.bindings["frozen_assessments"][cohort]["sha256"], "Assessment/frozen binding changed")
    same(assessment.get("receipt_version"), "wfg.forecast-assessment/2", "Assessment schema changed")
    expected_json = {record["case_id"] for record in records}
    scored_ids = {record["case_id"] for record in records if record["status"] == "SCORED"}
    if ({p.stem for p in (directory/"cases").glob("*.json")} != expected_json
            or {p.stem for p in (directory/"cases").glob("*.npz")} != scored_ids):
        raise AdmissionError("Unlisted/missing canonical case artifacts")
    for record in records:
        receipt_name = str((directory/"cases"/(record["case_id"]+".json")).relative_to(a.root))
        same(a.files.json(a.input(receipt_name)), record, "Individual case and assessment JSON differ")
        if record["status"] == "SCORED":
            array_name = str((directory/"cases"/(record["case_id"]+".npz")).relative_to(a.root))
            same(a.input(array_name).sha256, record.get("sha256"), "Case prediction/input hash differs")
        elif not record.get("reason"):
            raise AdmissionError("Unscored cases need their original explicit reason")
    if set(assessment["per_fire_files"]) != {p.name for p in directory.glob("*.npz")}:
        raise AdmissionError("Missing/extra canonical per-fire artifacts")
    for name, digest in assessment["per_fire_files"].items():
        same(a.input(str((directory/name).relative_to(a.root))).sha256, digest, "Per-fire input/receipt hash differs")
    entries = sum(r.get("scored_cells", 0) for r in records if r["status"] == "SCORED")
    summary = dict(assessment_status=assessment["status"], events=len(events), cases=len(records), statuses=statuses,
                   scored_fires=len(assessment["per_fire_files"]), entries=entries)
    same(a.review["cohorts"][folder], summary, "Independent canonical result child summary changed")
    frozen = a.frozen_assessments[cohort]
    same(frozen.get("selection_sha256"), a.bindings["selection"]["sha256"], "Frozen selection mismatch")
    same(frozen.get("registry"), a.bindings["registry"], "Frozen registry mismatch")
    for name, digest in frozen.get("source_sha256", {}).items():
        if name not in a.frozen or a.frozen[name].sha256 != digest:
            raise AdmissionError("Frozen assessment source lies outside the exact223 root bookend")
    # Identity-only metadata above establishes whether full supported scoring exists.
    complete = (assessment["status"] == "COMPLETE" and statuses == {"SCORED": spec["expected_cases"]}
                and len(assessment["per_fire_files"]) == len(spec["fire_order"]) and entries > 0)
    if not complete:
        return dict(cohort=cohort, status="UNAVAILABLE_COMPLETE_CANONICAL_SUPPORT", complete_cohort=False, metrics=None,
                    original_outcomes=assessment["failed_or_unavailable"], canonical_summary=summary,
                    promotion_criteria_pass=False)
    if metadata_only:
        return dict(cohort=cohort, metadata_complete=True)
    cases = []
    for record in records:
        identity = record["case"]
        receipt_rel = str((directory/"cases"/(record["case_id"]+".json")).relative_to(a.root))
        entries_rel = str((directory/"cases"/(record["case_id"]+".npz")).relative_to(a.root))
        receipt_pin, entries_pin = a.input(receipt_rel), a.input(entries_rel)
        if record.get("sha256") != entries_pin.sha256:
            raise AdmissionError("Root input map differs from original case prediction receipt")
        with a.files.npz(entries_pin) as raw:
            row, col, y = raw["row"], raw["col"], raw["y"]
        fields = {name: record[name] for name in SOURCE_FIELDS}
        cases.append(ExpectedCase(record["case_id"], identity, fields, receipt_pin, entries_pin,
            array_sha(row), array_sha(col), array_sha(y), record["scored_mask_sha256"], record["scored_cells"], record["positives"]))
    per_fire = {event: a.input(str((directory/(event+".npz")).relative_to(a.root))) for event in spec["fire_order"]}
    bindings = a.bindings
    sources = tuple(a.frozen.values())
    prerequisites = tuple(artifact_pointer(a.root, pointer) for pointer in a.authorization["prerequisite_receipts"].values())
    all_inputs = tuple(a.inputs.values())
    return CohortExpectation(cohort, directory, artifact_pointer(a.root, bindings["assessments"][cohort]),
        artifact_pointer(a.root, bindings["frozen_assessments"][cohort]), artifact_pointer(a.root, bindings["results"]),
        tuple(cases), per_fire, sources, all_inputs, prerequisites, object_sha(identity_map(sources)),
        object_sha(identity_map(all_inputs)), object_sha(identity_map(prerequisites)))


@contextmanager
def exclusive_heavy():
    lease = Path("/tmp/wfg/HEAVY.lock")
    lease.parent.mkdir(parents=True, exist_ok=True)
    with lease.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def run_authorized(authorized):
    """Only saved data, under an exclusive lease, into an exclusive new directory."""
    a = authorized
    outputs = {}
    # No scientific field is loaded before all root/global prerequisite identities pass.
    with exclusive_heavy():
        expectations = {}
        for cohort in ("us2024", "korea2025"):
            expectations[cohort] = cohort_expectation(a, cohort, metadata_only=True)
        a.out.mkdir(parents=True, exist_ok=False)
        for cohort in ("us2024", "korea2025"):
            expected = expectations[cohort]
            if not expected.get("metadata_complete"):
                outputs[cohort] = expected
                continue
            try:
                expected = cohort_expectation(a, cohort)
                cohort_files = verify_cohort(expected)
                if isinstance(cohort_files, dict):
                    outputs[cohort] = cohort_files
                    continue
                result, draws = compute_cohort(cohort, cohort_files.labels, cohort_files.model, cohort_files.points)
                result["execution_status"] = "ROOT_AUTHORIZED_SAVED_OUTPUT_COMPUTATION"
                result["draw_matrix"] = save_draws(a.out/(cohort+"_draws.npy"), draws)
                result["artifact_hashes_after"] = cohort_files.after()
                result["status"] = "AVAILABLE_DESCRIPTIVE_COMPLETE_COHORT"
                outputs[cohort] = result
            except (AdmissionError, ValueError, KeyError, TypeError) as error:
                outputs[cohort] = dict(cohort=cohort, status="UNAVAILABLE_ADMISSION_FAILURE", metrics=None,
                                      complete_cohort=False, reason=str(error), promotion_criteria_pass=False)
        after = a.files.unchanged()
        complete = all(value.get("status") == "AVAILABLE_DESCRIPTIVE_COMPLETE_COHORT" for value in outputs.values())
        result = dict(schema="wfg.current-descriptive-intervals/1", status="COMPLETE_DESCRIPTIVE_SUPPLEMENT" if complete else "INCOMPLETE_COHORTS_EXPLICITLY_UNAVAILABLE",
            method_protocol_sha256=PROTOCOL_SHA256, prerequisite_spec_sha256=PREREQUISITE_SHA256,
            root_authorization_sha256=a.authorization_sha256,
            canonical_bindings=a.bindings, frozen_files_sha256=a.authorization["frozen_files_sha256"],
            consumed_artifacts_before_after_sha256=after, dependencies=dependencies(),
            point_estimator_source_sha256=BASELINES_SHA256, point_estimator_ast_sha256=frozen_point_engine().ast_identity,
            cohorts=outputs, frozen_primary_unchanged=True, model_inference=False, promotion_criteria_pass=False,
            interpretation=protocol()["interpretation"],
            trust_boundary="Exogenous root authorization hash binds bytes; this software does not authenticate a human author or independent reviewer's identity")
        source_blob = Path(__file__).read_bytes()
        with (a.out/"supplement_source.py.gz").open("xb") as stream:
            stream.write(gzip.compress(source_blob, mtime=0))
        result["executed_source_sha256"] = sha_bytes(source_blob)
        write_new(a.out/"DESCRIPTIVE_INTERVALS.json", result)
        lines = ["# Separate descriptive interval supplement", "", result["status"], "", protocol()["interpretation"],
                 "", "Canonical primary decisions and every original artifact are unchanged.", ""]
        for cohort, record in outputs.items():
            lines += ["## " + cohort, "", record["status"], ""]
            if "models" not in record:
                lines += ["Complete-cohort intervals unavailable; original outcomes and reasons are retained in JSON.", ""]
                continue
            lines += ["| Model | Metric | Pooled point | Full whole-fire95% interval | Undefined draws |", "| --- | --- | --- | --- | --- |"]
            for name in protocol()["model_order"]:
                for field, metric in record["models"][name].items():
                    lines.append(f"| {name} | {field} | {metric['point']} | {metric['percentile_95_interval']} | {metric['undefined_union_draws']} |")
            lines += ["", "Defined-draw intervals in JSON are explicitly conditional, not replacements for unavailable full intervals.",
                      "Paired AP differences versus both fixed references are secondary descriptors, positive favouring candidate.", ""]
        with (a.out/"README.md").open("x") as stream:
            stream.write("\n".join(lines))
        a.files.unchanged()
        # A failed late bookend leaves a preserved partial directory, never this
        # completion receipt. Existing directories cannot be resumed/overwritten.
        write_new(a.out/"COMPLETION.json", dict(status="COMPLETED_SAVED_OUTPUT_COMPUTATION",
            result_sha256=sha_bytes((a.out/"DESCRIPTIVE_INTERVALS.json").read_bytes()),
            readme_sha256=sha_bytes((a.out/"README.md").read_bytes()),
            executed_source_sha256=result["executed_source_sha256"],
            cohort_statuses={name: value["status"] for name, value in outputs.items()},
            promotion_criteria_pass=False))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--authorization-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.protocol.resolve() != HERE/"method/DESCRIPTIVE_INTERVAL_PROTOCOL_V1.json":
        raise AdmissionError("Execute this exact bundled method protocol")
    dependencies()
    allowed = authorize(args.model_root, args.run, args.results, args.out, args.authorization, args.authorization_sha256)
    return run_authorized(allowed)


if __name__ == "__main__":
    main()
