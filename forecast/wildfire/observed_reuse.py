"""Authenticate and copy completed observed evaluations without re-simulation.

Stored predictions retain their original implementation and reference provenance.
Only exact current or explicitly pinned historical prediction signatures enter
this workflow; a reporting change never authorizes arbitrary inference drift.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from .observed_data import ARCHIVE_SHA256, DOI
from .observed_evaluation import M548_SHA256
from .paths import WORKSPACE


PRESENTATION_MODULES = frozenset(("observed_combined.py", "observed_reuse.py",
    "progress.py", "observed_report_plots.py", "cumulative_report_plots.py"))

# Verified against the immutable protocol of the user's 2026-10-12 run before
# the caching optimization. This is a trusted literal, not a caller's whitelist.
HISTORICAL_PREDICTION_SIGNATURE = {
    "observed_inventory.py": "5f352dfcc02ac7389377af6d90c15fae2262398bfcaccd87565397a64ee7e16b",
    "observed_catalog_data.py": "ab8613df1d68f04f26794212c45ce55737dfaa0df60189f44b0662cc83988da3",
    "observed_evaluation.py": "18832d7da19516e608a13b54680b9c15565258117ffafacd4a963c7b06404e11",
    "observed_data.py": "1476966182e6bf0016bbe4e48f44ad9381a3d3cb2ab618e888b5e1c2df6209ff",
    "rollout.py": "c09a23dabee9fe22dcbc9be23974defba2594ecd5ec59325e16b65268ef8405d",
    "api.py": "26efa71be6280f11cf3b68458bbcbb0f4509dd2c481a03b7e2517bda1baa9903",
    "inference.py": "c1278e491a23633e693854417e21bd1376060b638f3c3bf9f81ecc147c17dce6",
    "models.py": "52e1f29859f71dccf61b36a89df6b7863060fd25cc64fbc149500813f13e6722",
    "prediction.py": "c103a817f1ce87997a14291443d304f122afafec6ba3250136ecc979cb15d578",
    "cumulative.py": "0334ecacbfed8d31397378172c325a0ac2385798023c6a3efadc34ab1db119a7",
    "schema.py": "91d498f2c40e5f64138b0fe7a7845b2e4f522d086cdb9c4950ca9ed2c2043605",
    "coordinates.py": "9a9f56a60083bdb9e2990ca710280bfd75b7c004f2648d0af3d45a4f5c5a3dd3",
    "cumulative_report.py": "a8f30e5670fd1e8e5a0c4c8d164bac10d4f9c9b326aabf22441ae6b3fbb6fc81",
    "cohort.py": "68e65cba636c9dbc16357ddcb4f58cc18fecd5086c37c7e188bef4a5000e209a",
    "utils.py": "4b1ee9d08a30c1d423c2a70bc6e520dcea3ee01c67de8a6e4ca938cbf9305c92",
    "paths.py": "b26f7cc4621366582f253ff6962eeb371016931324d5787bcb1c99b486a5b4a5",
    "data.py": "8fb447ab28475e1909290e3b5af7717daace02db92655ff6f049861118d63230",
    "farsite_inputs.py": "259faf189bf0a94d11682d7845060f89dcc86c45e0c4bac21e698a4d00c564e6",
    "farsite_evaluation.py": "85d80c050b44f7548ae7511cdccf258e5dd85856aea38fd9953c1e6090aaf048",
    "farsite_report.py": "52c8879021278eeb4942ba6eb60bd87b6c824e09bd87c66ae619e86839ed0e06",
    "farsite_build.py": "d1c9830de57a21688e0c8c64bc38bd4334eff53d9a533fe818b28264f617d783",
    "farsite_observed_build.py": "187f210d990361864d52c4ae1d1a1a15452b63688969b4e2b50eb081da5328c4",
    "metrics.py": "7e3277e50f31c18ae042aa649793791d77840efaf9c0d3b02b8207bd2d1f9a93",
    "cumulative_evaluation.py": "071ec17bc1086f07e837da732536bc5ec913f25ac1709ca78bc3475a8f1c4b01",
}

EXPORT_FILES = ("report.json", "reference.npz", "m548_prediction.npz", "farsite_prediction.npz")
CONTROL_FIELDS = ("n_samples", "seed", "trajectory_batch_size", "threads", "threshold",
    "timestep_minutes", "timeout_seconds")
PATH_FIELDS = ("data_root", "archive", "prepared_directory", "observations_dir", "checkpoint")
CASE_FIELDS = ("event", "case_id", "cutoff", "endpoint", "hours", "duration_minutes",
    "source_record_ids", "m548_exposure")


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path):
    if Path(path).is_symlink():
        raise ValueError(f"Stored authentication files must not be symlinks: {path}")
    result = json.loads(Path(path).read_text())
    if not isinstance(result, dict):
        raise ValueError(f"Stored authentication object must be a mapping: {path}")
    return result


def prediction_signature(protocol):
    signature = protocol.get("implementation_sha256")
    if not isinstance(signature, dict):
        raise ValueError("Stored run has no complete prediction implementation signature")
    return {name: digest for name, digest in signature.items() if name not in PRESENTATION_MODULES}


def _engine_path(value):
    return Path(value or (WORKSPACE / "tmp/farsite_observed_source/src/TestFARSITE")).resolve()


class MissingStoredCase(RuntimeError):
    """A selected authentic case has no completed stored result to copy."""
    def __init__(self, case_id, status="missing", reason=None):
        self.case_id, self.status, self.reason = case_id, status, reason
        super().__init__(str(case_id) if reason is None else f"Stored case {case_id} is {status}: {reason}")


@dataclass(frozen=True)
class ReuseSource:
    directory: Path
    protocol: dict
    report: dict
    config: object
    protocol_sha256: str
    report_sha256: str
    implementation_kind: str

    @property
    def binding(self):
        return dict(source_directory=str(self.directory), source_protocol_sha256=self.protocol_sha256,
            source_report_sha256=self.report_sha256, prediction_origin=self.implementation_kind,
            source_prediction_implementation=prediction_signature(self.protocol), models_reexecuted=False)

    def _validate_native_and_reference(self, report, case):
        models = report.get("models")
        if (not isinstance(models, list) or len(models) != 2
                or models != self.report.get("models")
                or models[0].get("model_id") != "M548" or models[0].get("sha256") != M548_SHA256
                or models[1].get("model_id") != "FARSITE"):
            raise ValueError("Stored case model identities differ from its authenticated root run")
        if Path(models[0].get("path", "")).resolve() != Path(self.config.checkpoint).resolve():
            raise ValueError("Stored M548 model path differs from the selected original checkpoint")
        engine = report.get("engine", {})
        executable = _engine_path(self.config.engine)
        if (Path(models[1].get("path", "")).resolve() != executable
                or Path(engine.get("executable", "")).resolve() != executable
                or engine.get("executable_sha256") != models[1].get("sha256")
                or not engine.get("clock_loading_changes") or engine.get("spread_physics_changes") is not False
                or _sha256(executable) != engine.get("executable_sha256")):
            raise ValueError("Stored FARSITE model or minute-preserving engine identity is invalid")
        current_manifest = _json(executable.parent.parent / "observed_build_manifest.json")
        if current_manifest != engine:
            raise ValueError("Stored FARSITE engine differs from the current authenticated build manifest")
        probe = Path(engine.get("native_clock_probe", ""))
        if probe.is_symlink() or _sha256(probe) != engine.get("native_clock_probe_sha256"):
            raise ValueError("Stored FARSITE native clock probe identity is invalid")
        physical = report.get("farsite_input_manifest", {})
        if (physical.get("event_id") != case["event"] or physical.get("cutoff_utc") != case["cutoff"]
                or physical.get("endpoint_utc") != case["endpoint"]
                or physical.get("hours") != case["hours"]
                or physical.get("timestep_minutes") != self.config.timestep_minutes):
            raise ValueError("Stored FARSITE physical interval or native time step disagrees with the case")
        clock = physical.get("clock", {})
        start, end = datetime.fromisoformat(clock["start_local"]), datetime.fromisoformat(clock["end_local"])
        loaded = report.get("native_clock_verification", {})
        if (loaded.get("duration_minutes") != case["duration_minutes"]
                or loaded.get("start_hhmm") != start.hour * 100 + start.minute
                or loaded.get("end_hhmm") != end.hour * 100 + end.minute
                or (end - start).total_seconds() != case["duration_minutes"] * 60):
            raise ValueError("Stored actual native clock does not match its exact survey interval")
        for source in physical.get("source_files", []) + [physical.get("grid_source", {})]:
            try:
                relative = str(Path(source["path"]).resolve().relative_to(Path(self.config.data_root).resolve()))
            except (KeyError, ValueError) as error:
                raise ValueError("Stored FARSITE source binding is outside its authenticated data root") from error
            if self.protocol["input_sha256"].get(relative) != source.get("sha256"):
                raise ValueError("Stored FARSITE source differs from its authenticated covariate hash")
        observations = report.get("observations", {})
        publisher = observations.get("publisher_provenance", {})
        path = Path(observations.get("path", ""))
        if (observations.get("reconstructed_fire_labels_used") is not False
                or observations.get("same_rectangle_for_both_models") is not True
                or publisher.get("archive_sha256") != ARCHIVE_SHA256 or publisher.get("dataset_doi") != DOI
                or publisher.get("incident_component") != case["event"]
                or publisher.get("source_record_ids") != case["source_record_ids"]
                or publisher.get("geojson_sha256") != observations.get("sha256")
                or path.is_symlink() or _sha256(path) != observations.get("sha256")):
            raise ValueError("Stored observed-reference provenance differs from the authentic selected component")
        source_protocol = report.get("protocol", {})
        if (source_protocol.get("method") != "matched_observed_perimeter"
                or source_protocol.get("full_rectangle") is not True
                or source_protocol.get("boundary") != "zero"
                or source_protocol.get("environment_policy") != "repeated_current"
                or source_protocol.get("duration_minutes") != case["duration_minutes"]
                or source_protocol.get("hours") != case["hours"]):
            raise ValueError("Stored prediction semantics differ from this observed cumulative comparison")
        signature = source_protocol.get("implementation_sha256", {})
        for name in ("observed_evaluation.py", "rollout.py", "data.py", "farsite_inputs.py", "metrics.py"):
            if signature.get(name) != self.protocol["implementation_sha256"].get(name):
                raise ValueError("Stored case prediction implementation disagrees with its authenticated root signature")

    def validate_case(self, case, ancestor_paths=()):
        """Authenticate an existing case and its complete, read-only reuse chain.

        A reporting run may contain exports from an older authenticated run.
        Their original implementation remains in the case report; it must be
        verified against that original run rather than the reporting code.
        """
        from .observed_combined import _validate_resume, case_entries
        ancestors = tuple(Path(path).resolve() for path in ancestor_paths)
        if self.directory in ancestors:
            raise ValueError("Stored prediction reuse provenance contains a cycle")
        chain = ancestors + (self.directory,)
        if (_sha256(self.directory / "protocol.json") != self.protocol_sha256
                or _sha256(self.directory / "report.json") != self.report_sha256):
            raise ValueError("Stored root protocol or report changed after authentication")
        saved = next((item for item in self.protocol["cases"] if item["case_id"] == case["case_id"]), None)
        if saved is None:
            raise MissingStoredCase(case["case_id"], "missing", "Case is outside this stored source's authenticated plan")
        if any(saved.get(name) != case.get(name) for name in CASE_FIELDS):
            raise ValueError("Stored selected case, interval, or component source records disagree")
        source = self.directory / "cases" / case["case_id"]
        if (self.directory / "cases").is_symlink() or source.is_symlink():
            raise ValueError("Stored case directory must not be a symlink")
        if not source.exists():
            raise MissingStoredCase(case["case_id"], "missing", "No stored case directory")
        report_path = source / "report.json"
        if not report_path.exists():
            raise MissingStoredCase(case["case_id"], "incomplete", "No completed case report")
        report = _json(report_path)
        if report.get("status") != "complete":
            raise MissingStoredCase(case["case_id"], report.get("status", "incomplete"),
                "Saved evaluation did not complete; source outputs are preserved")
        for name in EXPORT_FILES + ("combined_case_manifest.json", "protocol.json"):
            path = source / name
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Completed stored case has a missing or symlinked export: {name}")
        if _json(source / "protocol.json") != report.get("protocol"):
            raise ValueError("Stored case report and source protocol disagree")
        _validate_resume(source, case, self.config)
        source_manifest = _json(source / "combined_case_manifest.json")
        case_entries(source, case, self.config)
        origin = self.directory
        origin_kind = self.implementation_kind
        ancestry = []
        proof_path = source / "reuse_provenance.json"
        if proof_path.exists() or proof_path.is_symlink():
            proof = _json(proof_path)
            parent_path = Path(proof.get("source_directory", ""))
            if parent_path.resolve() in chain:
                raise ValueError("Stored prediction reuse provenance contains a cycle")
            parent_config = SimpleNamespace(**{**vars(self.config), "reuse_results": parent_path})
            parent = authenticate_reuse(parent_config, self.protocol)
            if (proof.get("source_protocol_sha256") != parent.protocol_sha256
                    or proof.get("source_prediction_implementation") != prediction_signature(parent.protocol)
                    or proof.get("prediction_origin") != parent.implementation_kind
                    or proof.get("models_reexecuted") is not False
                    or proof.get("copied_exports") != list(EXPORT_FILES)
                    or Path(proof.get("source_case_directory", "")).resolve()
                        != parent.directory / "cases" / case["case_id"]
                    or ("source_report_sha256" in proof
                        and proof["source_report_sha256"] != parent.report_sha256)):
                raise ValueError("Stored reuse provenance disagrees with its authenticated parent run")
            try:
                validated = parent.validate_case(case, ancestor_paths=chain)
            except MissingStoredCase as error:
                # A declared completed descendant requires its original case.
                # Broken provenance must not authorize fallback or simulation.
                raise ValueError("Completed reused case has no authentic completed parent case") from error
            parent_source = validated["directory"]
            if (proof.get("source_manifest") != validated["manifest"]
                    or source_manifest != validated["manifest"]
                    or report.get("models") != self.report.get("models")
                    or report != validated["report"]
                    or any(_sha256(source / name) != _sha256(parent_source / name)
                        for name in EXPORT_FILES + ("protocol.json",))):
                raise ValueError("Reused case exports differ from their authenticated parent case")
            origin = validated["origin_directory"]
            origin_kind = validated["prediction_origin"]
            ancestry = [parent.binding] + validated["reuse_ancestry"]
        else:
            self._validate_native_and_reference(report, case)
        if (_sha256(self.directory / "protocol.json") != self.protocol_sha256
                or _sha256(self.directory / "report.json") != self.report_sha256):
            raise ValueError("Stored root protocol or report changed after authentication")
        return dict(directory=source, report=report, manifest=source_manifest,
            prediction_origin=origin_kind, origin_directory=origin, reuse_ancestry=ancestry)

    def copy_case(self, case, target_dir):
        """Copy authenticated exports to a fresh case directory, preserving source bytes."""
        from .observed_combined import _validate_resume, case_entries
        validated = self.validate_case(case)
        source, source_manifest = validated["directory"], validated["manifest"]
        target = Path(target_dir)
        if target.is_symlink() or (target.exists() and any(target.iterdir())):
            raise ValueError("Reused case destination must be new or empty, without symlinks")
        resolved = target.resolve()
        if resolved == self.directory or self.directory in resolved.parents:
            raise ValueError("Reused case destination must not modify the stored source")
        created = not target.exists()
        target.mkdir(parents=True, exist_ok=True)
        copied = []
        try:
            for name in EXPORT_FILES + ("combined_case_manifest.json", "protocol.json"):
                shutil.copyfile(source / name, target / name)
                copied.append(target / name)
            _validate_resume(target, case, self.config)
            if _json(target / "combined_case_manifest.json") != source_manifest:
                raise ValueError("Stored export manifest changed while copying authenticated predictions")
            case_entries(target, case, self.config)
            provenance = dict(source_directory=str(self.directory), source_case_directory=str(source),
                source_protocol_sha256=self.protocol_sha256,
                source_report_sha256=self.report_sha256,
                source_prediction_implementation=prediction_signature(self.protocol),
                prediction_origin=self.implementation_kind,
                origin_directory=str(validated["origin_directory"]),
                origin_prediction_kind=validated["prediction_origin"],
                reuse_ancestry=validated["reuse_ancestry"],
                interpretation="Historical stored predictions; original inference, reference, and model provenance retained"
                    if self.implementation_kind == "historical" else
                    "Stored predictions from the current authenticated implementation; no model re-execution",
                source_manifest=source_manifest, copied_exports=list(EXPORT_FILES),
                models_reexecuted=False)
            (target / "reuse_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
            copied.append(target / "reuse_provenance.json")
            return provenance
        except BaseException:
            if created:
                shutil.rmtree(target)
            else:
                for path in copied:
                    path.unlink(missing_ok=True)
            raise


def authenticate_reuse(config, target_protocol):
    """Authenticate a compatible source once; never mutate or execute its contents."""
    requested = getattr(config, "reuse_results", None)
    if requested is None:
        return None
    path = Path(requested)
    if path.is_symlink():
        raise ValueError("Stored run directory must not be a symlink")
    directory = path.resolve()
    output = Path(config.output_dir).resolve()
    if directory == output or directory in output.parents or output in directory.parents:
        raise ValueError("Stored source and destination output directories must not overlap")
    protocol = _json(directory / "protocol.json")
    report = _json(directory / "report.json")
    if report.get("protocol") != protocol:
        raise ValueError("Stored root report and protocol disagree")
    if (protocol.get("checkpoint_sha256") != M548_SHA256
            or protocol.get("archive_sha256") != ARCHIVE_SHA256
            or protocol.get("test_only") is not True or protocol.get("split") != "test_only"):
        raise ValueError("Stored source is not the original checkpoint's authentic test-only comparison")
    for name in ("checkpoint_sha256", "archive_sha256", "partition_binding", "checkpoint_test_events",
                 "authenticated_split_sha256"):
        if protocol.get(name) != target_protocol.get(name):
            raise ValueError(f"Stored source differs from the authenticated target: {name}")
    source_options, target_options = protocol.get("configuration", {}), target_protocol.get("configuration", {})
    for name in CONTROL_FIELDS:
        if name not in source_options or source_options.get(name) != target_options.get(name):
            raise ValueError(f"Stored simulation control differs from the target: {name}")
    for name in PATH_FIELDS:
        if name not in source_options or name not in target_options:
            raise ValueError(f"Stored source has no authenticated path: {name}")
        if Path(source_options[name]).resolve() != Path(target_options[name]).resolve():
            raise ValueError(f"Stored source path differs from the target: {name}")
    if _engine_path(source_options.get("engine")) != _engine_path(target_options.get("engine")):
        raise ValueError("Stored native engine selection differs from the target")
    source_inputs = protocol.get("input_sha256", {})
    for name, digest in target_protocol.get("input_sha256", {}).items():
        if source_inputs.get(name) != digest:
            raise ValueError(f"Stored covariate binding differs from the target: {name}")
    source_signature, current_signature = prediction_signature(protocol), prediction_signature(target_protocol)
    if source_signature == current_signature:
        implementation_kind = "current"
    elif source_signature == HISTORICAL_PREDICTION_SIGNATURE:
        implementation_kind = "historical"
    else:
        raise ValueError("Stored prediction implementation is neither the current nor pinned historical signature")
    source_cases = protocol.get("cases", [])
    by_id = {case.get("case_id"): case for case in source_cases}
    if len(by_id) != len(source_cases):
        raise ValueError("Stored source declares duplicate case identities")
    declared = set(protocol.get("checkpoint_test_events", []))
    for case in source_cases:
        identity = f"{case['event']}|{case['cutoff']}|{case['endpoint']}"
        if (case.get("case_id") != hashlib.sha256(identity.encode()).hexdigest()[:20]
                or case.get("event") not in declared or case.get("m548_exposure") != "held_out_event"):
            raise ValueError("Stored source case identity is invalid or outside the original test partition")
    for case in target_protocol.get("cases", []):
        saved = by_id.get(case["case_id"])
        if saved is not None and any(saved.get(name) != case.get(name) for name in CASE_FIELDS):
            raise ValueError("Selected case, exact interval, or component source records differ from the stored plan")
    return ReuseSource(directory, protocol, report, config, _sha256(directory / "protocol.json"),
        _sha256(directory / "report.json"), implementation_kind)
