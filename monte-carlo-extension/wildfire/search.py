"""Kernel search workflows and portable launchers.

Each workflow keeps its candidate plan, constants, and dispatch methods in an
explicit namespace. All variants share the same models, data contracts, metrics,
and training helpers while preserving their original experiment behavior.
"""
from __future__ import annotations

from .paths import resolve_recorded_path, resolve_source_root

import argparse
import copy
import csv
import hashlib
import json
import math
import platform
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
import tempfile

from .cache import (
    CachedSplit,
    fit_normalization,
    load_split,
    cell_hour_identities,
    validate_split_metadata,
    validate_partition_disjointness,
    DEFAULT_SOURCE_CACHE,
    relocate_cache,
)
from .cohort import (
    common_indices,
    crop_split,
    native_indices,
    cohort_payload,
    cohort_summary,
)
from .inference import (
    load_single_trained_model,
    load_mixed_trained_model,
    load_neural_mixed_trained_model,
)
from .metrics import (
    fit_categorical_balance,
    validate_categorical_balance_settings,
    categorical_balance_settings as balance_settings_from_args,
    add_categorical_balance_arguments,
    categorical_group_metrics,
    brier,
    weighted_calibration,
    select_classification_threshold,
    probability_metrics_with_all,
)
from .models import (
    build_kernel_model,
    initialize_kernel_rate,
    kernel_model_configuration,
    EnvironmentConditionedConvolution,
    center_probability,
    PatchRandomForest,
    MixedNonnegativeKernel,
    build_mixed_kernel_model,
    initialize_mixed_kernel_rate,
    NeuralMixedNonnegativeKernel,
    build_neural_mixed_kernel_model,
    initialize_neural_mixed_kernel_rate,
)
from .paths import RUNS as PATH_RUNS, DATA_ROOT
from .schema import SCHEMA_KEYS, one_hot_groups
from .train import (
    fit_global_rate,
    SCHEDULES,
    learning_rate_at_step,
    validate_scheduler,
    strict_cuda_equivalence,
)
from .utils import write_json, choose_device

# Freeze the complete active Python source closure for every new protocol.
CANONICAL_TRAINING_SOURCE_FILES = tuple(
    sorted(path.name for path in Path(__file__).resolve().parent.glob("*.py"))
)


class Search:
    """Fresh nonnegative kernel searches with uninterrupted long training.

    The declared partitions, labels and inverse sampling weights come from one
    frozen 9x9 cache. Each model trains on its K-contact rows. Hyperparameters,
    epochs, finalists and classification thresholds use validation only. Final
    test predictions cover every base-cache row; comparison metrics use native
    K-contact and identical 3-contact cohorts. No early stopping is used.
    """

    __doc__ = __doc__.replace("\n    ", "\n")
    __file__ = __file__
    PatchRandomForest = staticmethod(PatchRandomForest)
    brier = staticmethod(brier)
    probability_metrics_with_all = staticmethod(probability_metrics_with_all)
    balance_settings_from_args = staticmethod(balance_settings_from_args)
    load_split = staticmethod(load_split)
    load_trained_model = staticmethod(load_single_trained_model)
    TRAINING_SOURCE_FILES = CANONICAL_TRAINING_SOURCE_FILES

    RUNS = PATH_RUNS
    DEFAULT_CACHE = RUNS / "20261009_weighted_stratified_split/prepared_all"
    DEFAULT_OUTPUT = RUNS / "20261009_unsigned_kernel_search_weighted_stratified_categorical_balanced"
    DEFAULT_SMOKE_OUTPUT = RUNS / "20261009_unsigned_kernel_smoke_weighted_stratified_categorical_balanced"
    SIZES = (3, 5, 7, 9)
    NEURAL_FAMILIES = ("legacy", "cnn", "mlp", "residual_mlp")


    @staticmethod
    def split_contract_fields(metadata):
        """Persist the sampling unit and the validation generalization claim."""
        validate_split_metadata(metadata, require_all_partitions=True)
        row_split = metadata.get("split_unit") == "cell_hour"
        scope = ("Within-fire cell-hour interpolation; overlapping spatial contexts and fire histories across train/validation"
                 if row_split else "Validation and test on whole fires absent from the training partition")
        fields = dict(split_unit="cell_hour" if row_split else "whole_fire",
                      generalization_scope=metadata.get("generalization_scope", scope))
        if row_split:
            fields["original_splits"] = metadata["original_splits"]
            fields["partition_identity"] = ["event_id", "time_utc", "row", "col"]
        return fields


    @staticmethod
    def split_description(protocol):
        """Plain-language split semantics for reports and learning diagnostics."""
        if protocol.get("split_unit") == "cell_hour":
            return ("Training and validation use disjoint cell-hour rows sampled from the pooled development fires. "
                    "Validation can share fires, overlapping spatial contexts, and fire histories with training, "
                    "so it evaluates within-fire cell-hour interpolation. "
                    "The test partition retains its original whole fires, which are absent from training and validation.")
        return "Training, validation, and test use distinct whole-fire partitions."


    @staticmethod
    def fit_native_balance(data, metadata, protocol, output):
        """Fit and bind optimization-only category weights on one native crop."""
        settings = protocol.get("categorical_balance_settings", validate_categorical_balance_settings())
        weights, audit = fit_categorical_balance(data, metadata, **settings)
        audit = dict(audit, row_identities_sha256=hashlib.sha256(cell_hour_identities(data).tobytes()).hexdigest())
        destination = output / "categorical_balance" / f"k{data.environment.shape[-1]}.json"
        if destination.exists():
            if json.loads(destination.read_text()) != audit:
                raise ValueError("Categorical balance report differs from the frozen native training cohort")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_json(destination, audit)
        return weights, audit


    @staticmethod
    def bind_tensor_balance(data, metadata, protocol, output, tensors, device):
        """Check the fitted weights and immutable report before fitting/resuming."""
        if tensors.categorical_balance is None:
            effective, audit = Search.fit_native_balance(data, metadata, protocol, output)
            tensors.optimization_weight, tensors.categorical_balance = effective, audit
            tensors.loss_weight = torch.from_numpy((effective / effective.mean()).astype(np.float32)).to(device)
        audit = tensors.categorical_balance
        digest = hashlib.sha256(np.ascontiguousarray(tensors.optimization_weight, dtype="<f8").tobytes()).hexdigest()
        identity_digest = hashlib.sha256(cell_hour_identities(data).tobytes()).hexdigest()
        destination = output / "categorical_balance" / f"k{data.environment.shape[-1]}.json"
        if not destination.exists():
            # The same tensor cache can start an independent output directory.
            # Reproduce its fit before creating that directory's audit artifact.
            _, reproduced = Search.fit_native_balance(data, metadata, protocol, output)
            if reproduced != audit:
                raise ValueError("Tensor categorical balancing differs from the native training cohort")
        expected_loss_weight = torch.from_numpy(
            (tensors.optimization_weight / tensors.optimization_weight.mean()).astype(np.float32)).to(device)
        if (audit.get("optimization_weights_sha256") != digest
                or audit.get("population_weights_sha256") != hashlib.sha256(
                    np.ascontiguousarray(data.weight, dtype="<f8").tobytes()).hexdigest()
                or audit.get("row_identities_sha256") != identity_digest
                or audit.get("settings") != protocol.get("categorical_balance_settings", validate_categorical_balance_settings())
                or json.loads(destination.read_text()) != audit
                or not torch.equal(tensors.loss_weight, expected_loss_weight)):
            raise ValueError("Categorical balance weights or report differ from the committed native cohort")
        return audit


    @staticmethod
    def validate_categorical_normalization(mean, std, metadata):
        """Prevent a new checkpoint from claiming raw indicators after scaling them."""
        indices = [index for group in one_hot_groups(metadata).values() for index in group]
        if not indices:
            return
        mean, std = np.asarray(mean), np.asarray(std)
        if mean.shape != (len(metadata["channels"]),) or std.shape != mean.shape:
            raise ValueError("Categorical normalization must match the saved channel order")
        if np.any(mean[indices] != 0) or np.any(std[indices] != 1):
            raise ValueError("Categorical one-hot normalization must retain raw 0/1 with mean=0 and scale=1")


    @staticmethod
    def verify_balance_reports(output, protocol, records):
        """Bind candidate summaries to the same immutable native-cohort reports."""
        settings = protocol["categorical_balance_settings"]
        for record in records:
            candidate = record.get("candidate", record)
            path = output / "categorical_balance" / f"k{candidate['kernel_size']}.json"
            audit = record.get("categorical_balance")
            if (not isinstance(audit, dict) or audit.get("settings") != settings
                    or not path.is_file() or json.loads(path.read_text()) != audit):
                raise ValueError("Categorical balance report differs from the saved candidate summary")


    @staticmethod
    def verify_checkpoint_balance(record):
        """Check the selected model's audit before reading test data."""
        if "candidate" in record:
            contract = torch.load(resolve_recorded_path(record["checkpoint"]), map_location="cpu", weights_only=True)["contract"]
            audit = contract.get("categorical_balance")
            settings = contract.get("categorical_balance_settings")
        else:
            metadata = PatchRandomForest.load(resolve_recorded_path(record["checkpoint"])).metadata
            audit = metadata.get("categorical_balance")
            settings = metadata.get("categorical_balance_settings")
        if (not isinstance(audit, dict) or audit != record.get("categorical_balance")
                or settings != audit.get("settings")):
            raise ValueError("Categorical balance audit differs from the selected checkpoint")


    @staticmethod
    def balance_description(protocol):
        settings = protocol.get("categorical_balance_settings", {})
        if settings.get("mode", "none") == "none":
            return "Categorical balancing is disabled; optimization retains the original population weights."
        return ("Categorical optimization weights are fitted only on each learner's raw native training crop, "
                "using the original inverse-inclusion-weighted frequency of each category's presence anywhere in that crop. "
                "Bounded inverse-square-root rarity factors multiply the original population weights for neural optimization "
                "and forest fitting. Neural loss divides the optimization-weighted Brier by the optimization-weighted "
                "training burn frequency. Continuous feature normalization and global-rate initialization use population weights; one-hot inputs retain raw 0/1. All reported population Brier "
                "curves, validation selection, thresholds, and test metrics retain the original population weights. "
                "Post-update optimization-weighted training Brier is saved separately from population training Brier. "
                "Native and matched category-presence group diagnostics use original population weights; groups can overlap "
                "and never replace the pooled validation selection criterion. "
                "This training objective emphasizes rare categorical contexts; it does not guarantee improved category or population performance.")


    @staticmethod
    def sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


    @staticmethod
    def candidate_plan():
        """A prespecified joint configuration search, not a full factorial grid."""
        configurations = [
            ("constant", 1, 1, 0., .01, 0.),
            ("linear", 1, 1, 0., .01, .0001),
            ("legacy", 16, 1, 0., .001, .0001),
            ("cnn", 32, 1, .15, .003, .001),
            ("mlp", 8, 2, 0., .003, 0.),
            ("mlp", 32, 2, .15, .003, .0001),
            ("mlp", 128, 2, .15, .003, .01),
            ("mlp", 32, 4, 0., .001, .1),
            ("residual_mlp", 32, 3, .15, .003, .001),
            ("residual_mlp", 128, 3, .15, .001, .01),
        ]
        plan = []
        for k in Search.SIZES:
            for index, (family, width, depth, dropout, lr, decay) in enumerate(configurations):
                plan.append(dict(id=f"k{k}_{family}_{index:02d}", kernel_size=k, family=family,
                                 hidden_channels=width, depth=depth, dropout=dropout,
                                 learning_rate=lr, weight_decay=decay))
        return plan


    @staticmethod
    def verify_protocol(protocol, cache):
        """Reject input/code drift before resuming or exposing test outcomes."""
        if str(cache.resolve()) != protocol["cache"]:
            raise ValueError("Cache path differs from the frozen experiment protocol")
        for name, expected in protocol["cache_sha256"].items():
            if Search.sha256(cache / name) != expected:
                raise ValueError(f"Cache integrity mismatch: {name}; use a new output directory for changed inputs")
        for name, expected in protocol["training_source_sha256"].items():
            if not (Path(__file__).parent / name).is_file() or Search.sha256(Path(__file__).parent / name) != expected:
                raise ValueError(f"Training source integrity mismatch: {name}; use a new output directory for changed code")


    @staticmethod
    def setup(output, cache, epochs, finalist_epochs, seed, forest_trees=100, *, balance_settings=None):
        balance_settings = validate_categorical_balance_settings(**(balance_settings or {}))
        output.mkdir(parents=True, exist_ok=True)
        path = output / "protocol.json"
        if path.exists():
            protocol = json.loads(path.read_text())
            for key, value in {"cache": str(cache.resolve()), "candidate_epochs": epochs,
                               "finalist_epochs": finalist_epochs, "seed": seed, "forest_trees": forest_trees,
                               "categorical_balance_settings": balance_settings}.items():
                if protocol[key] != value:
                    raise ValueError(f"Resume protocol mismatch: {key}")
            Search.verify_protocol(protocol, cache)
            return protocol
        metadata = json.loads((cache / "metadata.json").read_text())
        validate_split_metadata(metadata, require_all_partitions=True)
        if metadata["dt_hours"] != 1. or metadata["kernel_size"] != 9:
            raise ValueError("The experiment requires the frozen one-hour 9x9 base cache")
        hashes = {name: Search.sha256(cache / name) for name in ("metadata.json", "train.npz", "validation.npz", "test.npz")}
        source_checks = []
        root = resolve_source_root(metadata)
        for source in metadata.get("source_files", []):
            actual = root / source["path"]
            if not actual.is_file() or Search.sha256(actual) != source["sha256"]:
                raise ValueError(f"Source integrity mismatch: {actual}")
            source_checks.append(source["path"])
        sources = {name: Search.sha256(Path(__file__).parent / name) for name in Search.TRAINING_SOURCE_FILES}
        protocol = dict(cache=str(cache.resolve()), candidate_epochs=epochs, finalist_epochs=finalist_epochs,
                        seed=seed, forest_trees=forest_trees, kernel_sizes=list(Search.SIZES), candidates=Search.candidate_plan(),
                        training="Native K-contact cells from one frozen base sampling design; complete known context; current center unburned",
                        contact="At least one off-center cell already burned at time t inside centered KxK; cumulative reconstructed burned map, not active flame",
                        common="Identical original 9x9 cache rows with contact inside centered 3x3; original labels and inverse inclusion weights",
                        selection="Minimum float64 inverse-weighted common-contact validation Brier; checkpoint and hyperparameters before test",
                        long_finalists="One globally validation-selected candidate per neural family (legacy, cnn, mlp, residual_mlp), continued from last optimizer state to the full finalist epoch budget",
                        optimizer="AdamW, full-batch categorical optimization-weighted Brier/optimization prevalence, fixed learning rate, decay on all parameters, no early stopping",
                        prediction="All original base-cache rows, including no-contact inputs; neural kernel structural zero for known no-contact",
                        test_used_for_selection=False, cache_sha256=hashes, training_source_sha256=sources,
                        verified_source_files=len(source_checks), target="unburned at t becomes burned at exactly t+3600s",
                        limitations=["Retrospective reconstructed hourly labels; not independent observed active flames",
                                     "Best among the finite prespecified joint configurations; not a global optimum",
                                     "Four single-seed neural finalists; curves can suggest delayed generalization, not prove grokking or double descent"],
                        versions=dict(python=platform.python_version(), numpy=np.__version__, torch=str(torch.__version__)),
                        references=["https://arxiv.org/abs/2201.02177", "https://arxiv.org/abs/1912.02292"])
        protocol["categorical_balance_settings"] = balance_settings
        protocol.update(Search.split_contract_fields(metadata))
        protocol["training"] += "; split unit: " + protocol["split_unit"]
        protocol["smoke_verification_only"] = bool(metadata.get("smoke_verification_only", False))
        snapshot = output / "source_snapshot"
        snapshot.mkdir(exist_ok=True)
        for name in sources:
            (snapshot / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(__file__).parent / name, snapshot / name)
        write_json(path, protocol)
        return protocol


    @staticmethod
    def build(candidate, channels, device):
        if candidate["family"] == "legacy":
            model = EnvironmentConditionedConvolution(channels, candidate["kernel_size"], candidate["hidden_channels"])
        else:
            model = build_kernel_model(channels, candidate["kernel_size"], candidate["family"],
                                       candidate["hidden_channels"], candidate["depth"], candidate["dropout"])
        return model.to(device)


    @staticmethod
    def _pointwise(layer, value):
        """Exact affine/activation computation at one spatial output position."""
        if isinstance(layer, nn.Conv2d):
            return F.linear(value, layer.weight.flatten(1), layer.bias)
        if isinstance(layer, nn.Dropout2d):
            # At spatial shape 1x1, channel dropout equals scalar feature dropout.
            return F.dropout(value, layer.p, layer.training)
        if isinstance(layer, nn.Sequential):
            for member in layer:
                value = Search._pointwise(member, value)
            return value
        if hasattr(layer, "update"):
            return F.silu(value + Search._pointwise(layer.update, value))
        return layer(value)


    @staticmethod
    def cached_probability(model, features, burned):
        """Trusted validated feature path retaining the public model's parameters.

        Linear rather than 1x1 convolution avoids repeated GPU validation barriers.
        The full spatial first layer is a flattened dot product. CPU float64 and
        device float32 equivalence are checked before and after every fitted run.
        Dropout has the same law at the single output position.
        """
        network = model.kernel_network
        if isinstance(network, nn.Sequential):
            logits = Search._pointwise(network, features)
        elif hasattr(network, "logits"):
            logits = network.logits.reshape(1, -1).expand(len(features), -1)
        else:
            hidden = F.linear(features, network.spatial.weight.flatten(1), network.spatial.bias)
            logits = Search._pointwise(network.output, Search._pointwise(network.hidden, hidden))
        rate = (F.softplus(logits) * burned).sum(dim=1)
        return -torch.expm1(-rate)


    @dataclass
    class TensorData:
        features: torch.Tensor
        burned: torch.Tensor
        target: np.ndarray
        weight: np.ndarray
        target_tensor: torch.Tensor
        loss_weight: torch.Tensor
        common: np.ndarray
        optimization_weight: np.ndarray | None = None
        categorical_balance: dict | None = None


    @staticmethod
    def tensor_data(data, mean, std, family, device, common=None, *,
                    optimization_weight=None, categorical_balance=None):
        n = len(data)
        spatial = family in ("legacy", "cnn")
        shape = (n, data.environment.shape[1] * data.environment.shape[-1] ** 2) if spatial else (n, data.environment.shape[1])
        features = np.empty(shape, dtype=np.float32)
        for start in range(0, n, 4096):
            end = min(start + 4096, n)
            normalized = (data.environment[start:end] - mean[None, :, None, None]) / std[None, :, None, None]
            features[start:end] = normalized.reshape(end-start, -1) if spatial else normalized.mean(axis=(2, 3))
        burned = data.burned.reshape(n, -1).copy()
        burned[:, burned.shape[1] // 2] = 0.
        effective = np.asarray(data.weight if optimization_weight is None else optimization_weight, dtype=np.float64)
        if effective.shape != (n,) or not np.isfinite(effective).all() or not (effective > 0).all():
            raise ValueError("Optimization weights must be positive finite values aligned with training rows")
        weights = (effective / effective.mean()).astype(np.float32)
        return Search.TensorData(torch.from_numpy(features).to(device), torch.from_numpy(burned).to(device),
                          data.target, data.weight, torch.from_numpy(data.target).to(device),
                          torch.from_numpy(weights).to(device), np.arange(n) if common is None else common,
                          effective, categorical_balance)


    @staticmethod
    @torch.no_grad()
    def probabilities(model, tensors, batch_size=65536):
        model.eval()
        output = np.empty(len(tensors.target), dtype=np.float32)
        for start in range(0, len(output), batch_size):
            end = min(start+batch_size, len(output))
            output[start:end] = Search.cached_probability(model, tensors.features[start:end], tensors.burned[start:end]).cpu().numpy()
        if not np.isfinite(output).all() or not ((output >= 0) & (output <= 1)).all():
            raise RuntimeError("Nonfinite or out-of-range kernel predictions")
        return output


    @staticmethod
    @torch.no_grad()
    def verify_equivalence(model, data, mean, std, family, device):
        small = crop_split(data, model.kernel_size, np.arange(min(8, len(data))))
        env = torch.from_numpy(small.environment.copy()).to(device)
        env = (env - torch.tensor(mean, device=device)[None,:,None,None]) / torch.tensor(std, device=device)[None,:,None,None]
        burned = torch.from_numpy(small.burned.copy()).to(device)
        model.eval()
        features = env.flatten(1) if family in ("legacy", "cnn") else env.mean((2,3))
        cached = Search.cached_probability(model, features, burned.flatten(1))
        public_center = center_probability(model, env, burned)
        c = model.kernel_size // 2
        grid_center = model(burned, env).probability[:,0,c,c]
        device_error = float(torch.max(torch.abs(cached-grid_center)).cpu())
        if not torch.allclose(cached, public_center, atol=2e-6, rtol=2e-5) or not torch.allclose(cached, grid_center, atol=2e-6, rtol=2e-5):
            raise AssertionError(f"Cached/public model mismatch: {device_error}")
        reference = copy.deepcopy(model).cpu().double().eval()
        x, b = env.cpu().double(), burned.cpu().double()
        f = x.flatten(1) if family in ("legacy", "cnn") else x.mean((2,3))
        exact = Search.cached_probability(reference, f, b.flatten(1))
        grid = reference(b,x).probability[:,0,c,c]
        error = float((exact-grid).abs().max())
        if not torch.allclose(exact, grid, atol=1e-12, rtol=1e-12):
            raise AssertionError(f"Float64 cached/public model mismatch: {error}")
        return dict(device_float32_max_error=device_error, cpu_float64_max_error=error)


    @staticmethod
    def make_contract(candidate, metadata, protocol):
        k = candidate["kernel_size"]
        contract = dict(format_version=1, architecture="EnvironmentConditionedConvolution" if candidate["family"]=="legacy" else "LearnedNonnegativeKernel",
                        in_channels=len(metadata["channels"]), channels=metadata["channels"], kernel_size=k,
                        hidden_channels=candidate["hidden_channels"], dt_hours=1., center_rate=0.,
                        eligibility="at_least_one_burned_neighbor", target=protocol["target"],
                        kernel_constraint="nonnegative", output_link="one_hour_exponential", evaluation_grouping="pooled_countries",
                        population_condition=f"Known currently unburned target with complete K={k} context and at least one already-burned neighbor",
                        normalization="Continuous channels use training-only native K-contact population-weighted moments; one-hot channels retain raw 0/1 with mean=0 and scale=1",
                        event_ids=metadata["event_ids"], splits=metadata["splits"],
                        cache_metadata_sha256=protocol["cache_sha256"]["metadata.json"])
        if candidate["family"] != "legacy":
            contract["kernel_model"] = {"architecture":candidate["family"], "hidden_channels":candidate["hidden_channels"],
                                       "depth":candidate["depth"], "dropout":candidate["dropout"]}
        contract["categorical_balance_settings"] = protocol.get("categorical_balance_settings", validate_categorical_balance_settings())
        contract.update(Search.split_contract_fields(metadata))
        contract.update({key:metadata[key] for key in SCHEMA_KEYS if key in metadata})
        return contract


    @staticmethod
    def fit_candidate(candidate, train_data, validation_data, tensors, validation_tensors,
                      mean, std, global_baseline, metadata, protocol, output, device, epochs):
        Search.validate_categorical_normalization(mean, std, metadata)
        balance_audit = Search.bind_tensor_balance(train_data, metadata, protocol, output, tensors, device)
        folder = output / "candidates" / candidate["id"]
        folder.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(protocol["seed"])
        if device.type == "mps":
            torch.mps.manual_seed(protocol["seed"])
        model = Search.build(candidate, len(metadata["channels"]), device)
        initialize_kernel_rate(model, max(global_baseline["per_neighbor_rate_per_hour"], 1e-8))
        optimizer = torch.optim.AdamW(model.parameters(), lr=candidate["learning_rate"], weight_decay=candidate["weight_decay"])
        history_path, last_path = folder / "history.json", folder / "last.pt"
        history = []
        best_score = math.inf
        if last_path.exists():
            saved = torch.load(last_path, map_location=device, weights_only=True)
            if saved.get("candidate") != candidate or saved.get("device") != str(device):
                raise ValueError("Resume requires the same candidate configuration and training device")
            if saved.get("categorical_balance") != balance_audit:
                raise ValueError("Resume categorical balancing differs from the committed optimization weights")
            model.load_state_dict(saved["model_state_dict"])
            optimizer.load_state_dict(saved["optimizer_state_dict"])
            history = json.loads(history_path.read_text())[:saved["epoch"]]
            best_score = saved["best_validation_brier"]
            # Recover the last committed best checkpoint even if interruption
            # occurred between a subsequent best save and the next state snapshot.
            torch.save(saved["best_checkpoint"], folder / "checkpoint.pt")
            torch.set_rng_state(saved["cpu_rng_state"].cpu())
            if device.type == "mps":
                torch.mps.set_rng_state(saved["mps_rng_state"].cpu())
            if device.type == "cuda":
                torch.cuda.set_rng_state_all([s.cpu() for s in saved["cuda_rng_states"]])
        contract = Search.make_contract(candidate, metadata, protocol)
        contract["categorical_balance"] = balance_audit
        verification = Search.verify_equivalence(model, train_data, mean, std, candidate["family"], device)
        prevalence = float(np.sum(train_data.weight*train_data.target)/np.sum(train_data.weight))
        optimization_prevalence = float(np.dot(tensors.optimization_weight, train_data.target) / tensors.optimization_weight.sum())
        if not 0 < optimization_prevalence < 1:
            raise ValueError("Optimization requires positive and negative native training targets")
        started = time.perf_counter()
        start_epoch = len(history)
        for epoch in range(start_epoch+1, epochs+1):
            model.train()
            optimizer.zero_grad(set_to_none=True)
            # Chunked backward implements ONE full-batch optimizer step per epoch.
            # It reduces activation memory while retaining the fitted categorical optimization weights.
            loss_value = 0.
            n = len(train_data)
            for start in range(0,n,65536):
                end = min(start+65536,n)
                p = Search.cached_probability(model,tensors.features[start:end],tensors.burned[start:end])
                loss = (tensors.loss_weight[start:end]*(p-tensors.target_tensor[start:end]).square()).sum()/(n*optimization_prevalence)
                loss.backward()
                loss_value += float(loss.detach().cpu())
            gradient_norm = nn.utils.clip_grad_norm_(model.parameters(), max_norm=10., error_if_nonfinite=True)
            optimizer.step()
            p_train, p_val = Search.probabilities(model,tensors), Search.probabilities(model,validation_tensors)
            train_brier = brier(train_data.target,p_train,train_data.weight)
            optimization_train_brier = brier(train_data.target,p_train,tensors.optimization_weight)
            tc = tensors.common
            train_common_brier = brier(train_data.target[tc],p_train[tc],train_data.weight[tc])
            native_brier = brier(validation_data.target,p_val,validation_data.weight)
            ci = validation_tensors.common
            common_brier = brier(validation_data.target[ci],p_val[ci],validation_data.weight[ci])
            improved = common_brier < best_score
            if improved:
                best_score = common_brier
                checkpoint = dict(contract=contract,model_state_dict=model.state_dict(), normalization_mean=torch.from_numpy(mean.copy()),
                                  normalization_std=torch.from_numpy(std.copy()),best_epoch=epoch,validation_brier=best_score,
                                  configuration=candidate,global_rate_baseline=global_baseline,train_weighted_prevalence=prevalence,
                                  optimization_weighted_prevalence=optimization_prevalence)
                torch.save(checkpoint,folder/"checkpoint.pt")
            record = dict(epoch=epoch,train_brier=train_brier,train_common_brier=train_common_brier,validation_native_brier=native_brier,
                          validation_common_brier=common_brier,training_regularized_dropout_loss=loss_value,
                          optimization_weighted_prevalence=optimization_prevalence,population_weighted_prevalence=prevalence,
                          optimization_train_brier=optimization_train_brier,
                          gradient_norm=float(gradient_norm.cpu()),parameter_norm=math.sqrt(sum(float(p.detach().square().sum().cpu()) for p in model.parameters())),
                          selected=improved,elapsed_seconds=time.perf_counter()-started)
            history.append(record)
            if epoch%32==0 or epoch==epochs:
                write_json(history_path,history)
                state = dict(model_state_dict=model.state_dict(),optimizer_state_dict=optimizer.state_dict(),epoch=epoch,
                             best_validation_brier=best_score,cpu_rng_state=torch.get_rng_state(),candidate=candidate,device=str(device),
                             categorical_balance=balance_audit,
                             best_checkpoint=torch.load(folder/"checkpoint.pt", map_location="cpu", weights_only=True))
                if device.type=="mps":state["mps_rng_state"]=torch.mps.get_rng_state()
                if device.type=="cuda":state["cuda_rng_states"]=torch.cuda.get_rng_state_all()
                torch.save(state,last_path)
                print(f"{candidate['id']} epoch={epoch}/{epochs} train={train_brier:.7f} val_common={common_brier:.7f} best={best_score:.7f}",flush=True)
        selected = torch.load(folder/"checkpoint.pt",map_location=device,weights_only=True)
        model.load_state_dict(selected["model_state_dict"])
        verification["selected_checkpoint"] = Search.verify_equivalence(model,train_data,mean,std,candidate["family"],device)
        reloaded = Search.load_trained_model(folder/"checkpoint.pt",device)
        if not all(torch.equal(a,b) for a,b in zip(model.state_dict().values(),reloaded.model.state_dict().values())):
            raise AssertionError("Checkpoint parameters changed on public reload")
        summary = dict(candidate=candidate,epochs_completed=len(history),best_epoch=selected["best_epoch"],
                       validation_common_brier=best_score,checkpoint=str((folder/"checkpoint.pt").resolve()),
                       train_sample_count=len(train_data),validation_native_sample_count=len(validation_data),
                       validation_common_sample_count=len(validation_tensors.common),early_stopped=False,
                       checkpoint_sha256=Search.sha256(folder/"checkpoint.pt"),
                       trainable_parameters=sum(p.numel() for p in model.parameters()),verification=verification,
                       test_used_for_selection=False,device=str(device),categorical_balance=balance_audit,
                       population_weighted_prevalence=prevalence,optimization_weighted_prevalence=optimization_prevalence)
        write_json(folder/"summary.json",summary)
        return summary


    @staticmethod
    def train_search(args):
        protocol = Search.setup(args.output,args.cache,args.epochs,args.finalist_epochs,args.seed,args.forest_trees,
                         balance_settings=balance_settings_from_args(args))
        metadata = json.loads((args.cache/"metadata.json").read_text())
        train_base, validation_base = (Search.load_split(args.cache,name,metadata) for name in ("train","validation"))
        validate_partition_disjointness({"train": train_base, "validation": validation_base}, metadata)
        device = choose_device(args.device)
        torch.set_num_threads(args.threads)
        summaries = []
        balance_by_k = {}
        for k in Search.SIZES:
            ti,vi = native_indices(train_base,k),native_indices(validation_base,k)
            train_data, val_data = crop_split(train_base,k,ti),crop_split(validation_base,k,vi)
            balance_by_k[k] = Search.fit_native_balance(train_data, metadata, protocol, args.output)
            effective, balance_audit = balance_by_k[k]
            mean,std = fit_normalization(train_data, metadata=metadata)
            global_baseline = fit_global_rate(train_data)
            tci = np.flatnonzero(np.isin(ti,common_indices(train_base)))
            ci = np.flatnonzero(np.isin(vi,common_indices(validation_base)))
            for spatial in (False,True):
                family = "legacy" if spatial else "mlp"
                tensors, vt = Search.tensor_data(train_data,mean,std,family,device,tci,optimization_weight=effective,categorical_balance=balance_audit),Search.tensor_data(val_data,mean,std,family,device,ci)
                for candidate in [c for c in protocol["candidates"] if c["kernel_size"]==k and ((c["family"] in ("legacy","cnn"))==spatial)]:
                    summary_path=args.output/"candidates"/candidate["id"]/"summary.json"
                    if summary_path.exists() and json.loads(summary_path.read_text())["epochs_completed"]>=args.epochs:
                        recovered = json.loads(summary_path.read_text())
                        if recovered.get("categorical_balance") != balance_audit:
                            raise ValueError("Saved candidate summary categorical balancing differs from the native training cohort")
                        summaries.append(recovered)
                    else:
                        summaries.append(Search.fit_candidate(candidate,train_data,val_data,tensors,vt,mean,std,global_baseline,metadata,protocol,args.output,device,args.epochs))
                    write_json(args.output/"candidate_selection.json",summaries)
                del tensors,vt
                if device.type=="mps":torch.mps.empty_cache()
            del train_data,val_data
        frozen_finalists=args.output/"finalist_selection.json"
        if frozen_finalists.exists():
            before_extension=json.loads(frozen_finalists.read_text())["selection_before_extension"]
            candidates_by_id={s["candidate"]["id"]:s for s in summaries}
            finalists=[candidates_by_id[s["candidate"]["id"]] for s in before_extension]
        else:
            finalists = [min((s for s in summaries if s["candidate"]["family"]==family),key=lambda s:s["validation_common_brier"]) for family in Search.NEURAL_FAMILIES]
            write_json(frozen_finalists,dict(selection_before_extension=finalists,test_used_for_selection=False))
        for selected in finalists:
            c=selected["candidate"];k=c["kernel_size"]
            ti,vi=native_indices(train_base,k),native_indices(validation_base,k)
            td,vd=crop_split(train_base,k,ti),crop_split(validation_base,k,vi)
            effective, balance_audit = balance_by_k[k]
            mean,std=fit_normalization(td, metadata=metadata);baseline=fit_global_rate(td)
            ci=np.flatnonzero(np.isin(vi,common_indices(validation_base)))
            tci=np.flatnonzero(np.isin(ti,common_indices(train_base)))
            tensors,vt=Search.tensor_data(td,mean,std,c["family"],device,tci,optimization_weight=effective,categorical_balance=balance_audit),Search.tensor_data(vd,mean,std,c["family"],device,ci)
            extended=Search.fit_candidate(c,td,vd,tensors,vt,mean,std,baseline,metadata,protocol,args.output,device,args.finalist_epochs)
            summaries=[extended if s["candidate"]["id"]==c["id"] else s for s in summaries]
            write_json(args.output/"candidate_selection.json",summaries)
            del tensors,vt,td,vd
            if device.type=="mps":torch.mps.empty_cache()
        write_json(args.output/"neural_complete.json",dict(completed=True,candidates=len(summaries),long_finalists=len(finalists),test_used_for_selection=False))


    @staticmethod
    def forest_search(args):
        protocol=Search.setup(args.output,args.cache,args.epochs,args.finalist_epochs,args.seed,args.forest_trees,
                         balance_settings=balance_settings_from_args(args))
        metadata=json.loads((args.cache/"metadata.json").read_text())
        train_base,val_base=(Search.load_split(args.cache,n,metadata) for n in ("train","validation"))
        validate_partition_disjointness({"train": train_base, "validation": val_base}, metadata)
        selection=[]
        for k in (3,5):
            ti=native_indices(train_base,k)
            td=crop_split(train_base,k,ti)
            effective, balance_audit = Search.fit_native_balance(td, metadata, protocol, args.output)
            mean,std=fit_normalization(td, metadata=metadata)
            env=(td.environment-mean[None,:,None,None])/std[None,:,None,None]
            ci=common_indices(val_base)
            vd=crop_split(val_base,k,ci)
            ve=(vd.environment-mean[None,:,None,None])/std[None,:,None,None]
            best=None
            for depth in (8,15,None):
                name=f"rf{k}_depth{depth}"
                path=args.output/"forests"/f"{name}.joblib"
                path.parent.mkdir(parents=True,exist_ok=True)
                summary_path=path.with_suffix(".json")
                if summary_path.exists():
                    summary=json.loads(summary_path.read_text())
                    if summary.get("categorical_balance") != balance_audit:
                        raise ValueError("Saved forest summary categorical balancing differs from the native training cohort")
                else:
                    if path.exists():
                        # A completed forest save interrupted before its summary
                        # can be safely recovered without fitting or overwriting it.
                        model=PatchRandomForest.load(path)
                        if model.metadata.get("categorical_balance") != balance_audit:
                            raise ValueError("Saved forest categorical balancing differs from the native training cohort")
                    else:
                        model=PatchRandomForest(k,n_estimators=args.forest_trees,max_depth=depth,random_state=args.seed,n_jobs=args.threads)
                    start=time.perf_counter()
                    if not path.exists():model.fit(env,td.burned,td.target,effective,channel_names=metadata["channels"])
                    p=model.predict_probability(ve,vd.burned,channel_names=metadata["channels"])
                    score=brier(vd.target,p,vd.weight)
                    if not path.exists():model.save(path,metadata=dict(normalization_mean=mean.tolist(),normalization_std=std.tolist(),cache_metadata_sha256=protocol["cache_sha256"]["metadata.json"],categorical_balance=balance_audit,
                                                                        categorical_balance_settings=protocol["categorical_balance_settings"]))
                    reload=PatchRandomForest.load(path)
                    np.testing.assert_allclose(p,reload.predict_probability(ve,vd.burned,channel_names=metadata["channels"]),rtol=0,atol=1e-12)
                    summary=dict(id=name,family="random_forest",kernel_size=k,max_depth=depth,n_estimators=args.forest_trees,
                                 checkpoint=str(path.resolve()),validation_common_brier=score,train_sample_count=len(td),
                                 checkpoint_sha256=Search.sha256(path),
                                 fit_seconds=time.perf_counter()-start,test_used_for_selection=False,categorical_balance=balance_audit)
                    write_json(summary_path,summary)
                    print(f"{name} val_common={score:.7f} seconds={summary['fit_seconds']:.1f}",flush=True)
                selection.append(summary)
                if best is None or summary["validation_common_brier"]<best["validation_common_brier"]:best=summary
            del env,ve,td,vd
        write_json(args.output/"forest_selection.json",selection)
        write_json(args.output/"forests_complete.json",dict(completed=True,candidates=len(selection),test_used_for_selection=False))


    @staticmethod
    def thresholds(data,p,indices):
        return {name:select_classification_threshold(data.target[indices],p[indices],data.weight[indices],criterion=name) for name in ("f1","mcc")}


    @staticmethod
    def finalize(args):
        if not all((args.output/name).exists() for name in ("neural_complete.json","forests_complete.json")):
            raise ValueError("Neural and forest searches must finish before test evaluation")
        protocol=json.loads((args.output/"protocol.json").read_text())
        if protocol["categorical_balance_settings"] != balance_settings_from_args(args):
            raise ValueError("Resume protocol mismatch: categorical_balance_settings")
        Search.verify_protocol(protocol,args.cache)
        metadata=json.loads((args.cache/"metadata.json").read_text())
        summaries=json.loads((args.output/"candidate_selection.json").read_text())
        forests=json.loads((args.output/"forest_selection.json").read_text())
        Search.verify_balance_reports(args.output, protocol, summaries + forests)
        selected=[]
        for family in ("constant","linear",*Search.NEURAL_FAMILIES):
            for k in Search.SIZES:
                selected.append(min((s for s in summaries if s["candidate"]["family"]==family and s["candidate"]["kernel_size"]==k),key=lambda s:s["validation_common_brier"]))
        for k in (3,5):selected.append(min((s for s in forests if s["kernel_size"]==k),key=lambda s:s["validation_common_brier"]))
        best=min(selected,key=lambda s:s["validation_common_brier"])
        for record in selected:
            if record.get("checkpoint_sha256") != Search.sha256(record["checkpoint"]):
                raise ValueError(f"Selected checkpoint integrity mismatch: {record['checkpoint']}")
            Search.verify_checkpoint_balance(record)
        write_json(args.output/"selection.json",dict(selected=selected,best=best,test_used_for_selection=False))
        write_json(args.output/"best_models.json",{name:record for record in selected for name in [
            f"{record['candidate']['family']}_k{record['candidate']['kernel_size']}" if "candidate" in record
            else f"random_forest_k{record['kernel_size']}"]})
        # This is the first stage loading test inputs/outcomes.
        metrics={};calibration_thresholds={};identities={}
        for split in ("validation","test","train"):
            data=Search.load_split(args.cache,split,metadata)
            identities[split] = cell_hour_identities(data)
            common=common_indices(data)
            payload=cohort_payload(data,common)
            native_cohorts={k:native_indices(data,k) for k in Search.SIZES}
            rows={}
            for record in selected:
                if "candidate" in record:
                    c=record["candidate"];name=c["id"];k=c["kernel_size"]
                    fitted=Search.load_trained_model(record["checkpoint"],args.device)
                    cropped=crop_split(data,k)
                    mean=fitted.mean[:,0,0].cpu().numpy();std=fitted.std[:,0,0].cpu().numpy()
                    tensors=Search.tensor_data(cropped,mean,std,c["family"],choose_device(args.device))
                    p=Search.probabilities(fitted.model,tensors)
                    no_contact=cropped.neighbor_count==0
                    if not np.all(p[no_contact]==0):raise AssertionError("Kernel no-contact probabilities must be structural zeros")
                    coverage=dict(predicted_count=len(p),no_contact_count=int(no_contact.sum()),no_contact_probability_max=float(p[no_contact].max()) if no_contact.any() else None)
                    del tensors,fitted
                else:
                    name=record["id"];k=record["kernel_size"]
                    fitted=PatchRandomForest.load(resolve_recorded_path(record["checkpoint"]))
                    preprocessing=fitted.metadata
                    mean=np.array(preprocessing["normalization_mean"],dtype=np.float32);std=np.array(preprocessing["normalization_std"],dtype=np.float32)
                    cropped=crop_split(data,k)
                    p=np.empty(len(data),dtype=np.float64)
                    for start in range(0,len(data),8192):
                        end=min(start+8192,len(data));e=(cropped.environment[start:end]-mean[None,:,None,None])/std[None,:,None,None]
                        p[start:end]=fitted.predict_probability(e,cropped.burned[start:end],channel_names=metadata["channels"])
                    coverage=dict(predicted_count=len(p),no_contact_count=int((cropped.neighbor_count==0).sum()),no_contact_probability_max=float(p[cropped.neighbor_count==0].max()) if (cropped.neighbor_count==0).any() else None)
                ni=native_cohorts[k]
                if split=="validation":
                    reproduced=brier(data.target[common],p[common],data.weight[common])
                    if not math.isclose(reproduced,record["validation_common_brier"],rel_tol=0,abs_tol=2e-6):
                        raise AssertionError(f"Selected checkpoint validation score mismatch: {name}")
                    calibration_thresholds[name]={"common":Search.thresholds(data,p,common),"native":Search.thresholds(data,p,ni)}
                t=calibration_thresholds[name]
                rows[name]=dict(kernel_size=k,coverage=coverage,
                                native=probability_metrics_with_all(data.target[ni],p[ni],data.weight[ni],cropped.neighbor_count[ni],thresholds=t["native"]),
                                common=probability_metrics_with_all(data.target[common],p[common],data.weight[common],cropped.neighbor_count[common],thresholds=t["common"]))
                rows[name]["categorical_groups"] = {
                    "native": categorical_group_metrics(cropped, p, metadata, indices=ni),
                    "common": categorical_group_metrics(cropped, p, metadata, indices=common),
                }
                rows[name]["native"]["calibration"]=weighted_calibration(data.target[ni],p[ni],data.weight[ni])
                rows[name]["common"]["calibration"]=weighted_calibration(data.target[common],p[common],data.weight[common])
                payload[name]=p[common]
                dest=args.output/"predictions"/split;dest.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(dest/f"{name}.npz",p=p,source_index=np.arange(len(data)),native_index=ni,common_index=common)
            dest=args.output/"predictions";dest.mkdir(exist_ok=True)
            np.savez_compressed(dest/f"{split}_common.npz",**payload)
            metrics[split]=dict(common_cohort=cohort_summary(data,common,3),native_cohorts={str(k):cohort_summary(data,native_cohorts[k],k) for k in Search.SIZES},models=rows)
            write_json(args.output/"metrics.json",metrics)
            del data
        write_json(args.output/"classification_thresholds.json",calibration_thresholds)
        partition_verification = validate_partition_disjointness(identities, metadata)
        write_json(args.output/"partition_verification.json", partition_verification)
        Search.report(args.output,protocol,selected,best,metrics)
        Search.verify_protocol(protocol,args.cache)
        write_json(args.output/"complete.json",dict(completed=True,neural_candidates=len(summaries),forest_candidates=len(forests),evaluated_models=len(selected),
                                                  test_used_for_selection=False,cache_sha256_verified={n:Search.sha256(args.cache/n)==v for n,v in protocol["cache_sha256"].items()}))


    @staticmethod
    def report(output,protocol,selected,best,metrics):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        def label(s):
            c=s.get("candidate",s)
            return f"{c.get('family')} {c['kernel_size']}x{c['kernel_size']}"
        def name(s):return s.get("candidate",s)["id"]
        def fmt(v):return f"{v:.6f}" if isinstance(v,(float,int)) else str(v)
        partition_description = Search.split_description(protocol)
        lines=["# Fresh unsigned kernel model search", "",f"Validation selected **{label(best)}** among the searched configurations. All test scores below were computed after selection.","",
               partition_description,"",Search.balance_description(protocol),"",
               "The target is a currently unburned cell becoming burned at exactly the next hourly snapshot. Contact uses the reconstructed current cumulative burned-area map; it does not mean an actively flaming cell.","",
               f"Every candidate completed {protocol['candidate_epochs']} full-batch epochs. One validation-selected candidate in each of four neural families continued, with optimizer and RNG state, to {protocol['finalist_epochs']} epochs. There was no early stopping. A saved prediction checkpoint can occur before the final epoch because selection minimizes validation Brier over the entire trajectory.","",
               "All fits are fresh. Constant kernels learn offset-specific rates; linear kernels map per-channel environmental patch means to nonnegative rates; MLP and residual MLP families use the same patch means; the existing CNN and new regularized CNN preserve full spatial environmental patches. Every kernel fixes its center to zero and computes q=1-exp(-sum(nonnegative offset rate × current burned neighbor)). Random forests are separate probability-classifier baselines, not learned rate kernels.","",
               "Training uses native K-contact rows from one frozen 9x9 sample cache and its original inverse inclusion weights. Native evaluation also uses K-contact. The matched comparison uses the exact same current 3x3-contact rows for every model, retaining the original weights. No-contact predictions are saved for every model; neural kernels return a valid structural zero, and forests may return nonzero probabilities.","",
               "Optimization is AdamW with fixed learning rate, full-batch categorical optimization-weighted Brier divided by optimization-weighted training prevalence, weight decay, optional dropout, and gradient norm clipping at 10. An epoch is one pass over every native training row and ONE optimizer step, with chunked gradient accumulation. It is not equivalent to the earlier minibatch update schedule. The joint configuration search varies widths 8/16/32/128, neural depths 1/2/3/4, dropout 0/0.15, learning rates 0.001/0.003 (0.01 for simpler kernels), and weight decay 0/0.0001/0.001/0.01/0.1. This is a finite designed search, not a full factorial or proof of global optimality.","",
               "## Matched test comparison", "", "| Model | Completed / selected epoch | Validation Brier | Test Brier | AP | ROC AUC | Exact NLL | F1 at validation threshold | MCC at validation threshold |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        csv_rows=[]
        for s in sorted(selected,key=lambda s:s["validation_common_brier"]):
            n=name(s);m=metrics["test"]["models"][n]["common"]
            epoch=f"{s['epochs_completed']} / {s['best_epoch']}" if "epochs_completed" in s else "trees"
            lines.append(f"| {label(s)} | {epoch} | {fmt(s['validation_common_brier'])} | {fmt(m['brier'])} | {fmt(m['average_precision'])} | {fmt(m['roc_auc'])} | {fmt(m['exact_negative_log_likelihood_mean'])} | {fmt(m['f1_at_validation_f1_threshold'])} | {fmt(m['mcc_at_validation_mcc_threshold'])} |")
            csv_rows.append(dict(model=n,label=label(s),validation_brier=s["validation_common_brier"],**{key:value for key,value in m.items() if not isinstance(value,(list,dict))}))
        lines += ["", "## Cohort sizes", "", "| Split | Full prediction rows | 3x3 contact | 5x5 contact | 7x7 contact | 9x9 contact | Matched positives |", "|---|---:|---:|---:|---:|---:|---:|"]
        for split in ("train","validation","test"):
            c=metrics[split];lines.append(f"| {split} | {c['common_cohort']['base_sample_count']} | " + " | ".join(str(c["native_cohorts"][str(k)]["sample_count"]) for k in Search.SIZES)+f" | {c['common_cohort']['positive_sample_count']} |")
        lines += ["", "## Native test comparison", "", "These scores use different K-contact populations and therefore cannot rank kernel sizes fairly. Compare model families within the same K, or use the matched table above.","", "| Model | Native test Brier | Native AP | Native ROC AUC |", "|---|---:|---:|---:|"]
        for s in selected:
            m=metrics["test"]["models"][name(s)]["native"]
            lines.append(f"| {label(s)} | {fmt(m['brier'])} | {fmt(m['average_precision'])} | {fmt(m['roc_auc'])} |")
        fig,axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
        diagnostics={}
        for ax,family in zip(axes.flat,Search.NEURAL_FAMILIES):
            s=min((x for x in selected if x.get("candidate",{}).get("family")==family),key=lambda x:x["validation_common_brier"])
            h=json.loads((output/"candidates"/name(s)/"history.json").read_text())
            x=np.array([r["epoch"] for r in h]);v=np.array([r["validation_common_brier"] for r in h]);tr=np.array([r["train_common_brier"] for r in h])
            ax.plot(x,tr,label="matched training Brier");ax.plot(x,v,label="matched validation Brier")
            ax.axvline(protocol["candidate_epochs"],color="gray",linestyle=":",label="end of initial search")
            ax.scatter([s["best_epoch"]],[s["validation_common_brier"]],color="red",s=25,zorder=4,label="selected checkpoint")
            ax.set(xscale="log",xlabel="Epoch (log scale)",ylabel="Weighted Brier",title=f"{label(s)}; full {len(h)} epochs")
            ax.legend(fontsize=8)
            early=min(v[:protocol["candidate_epochs"]]);late=min(v[protocol["candidate_epochs"]:]) if len(v)>protocol["candidate_epochs"] else None
            diagnostics[family]=dict(candidate=name(s),best_first_stage_validation_brier=float(early),best_late_validation_brier=float(late) if late is not None else None,
                                     relative_late_improvement=(float((early-late)/early) if late is not None else None),
                                     best_epoch=s["best_epoch"],final_training_brier=float(tr[-1]),minimum_training_brier=float(tr.min()),
                                     interpretation="Descriptive late improvement only. " + partition_description + " No verified interpolation threshold or multi-seed grokking claim.")
        fig.savefig(output/"learning_curves.png",dpi=180);plt.close(fig)
        write_json(output/"learning_diagnostics.json",diagnostics)
        lines += ["", "## Long-training observations", "", "![Learning curves](learning_curves.png)","",
                  f"These curves show training and validation Brier under the same current 3x3-contact condition. {partition_description} Native training Brier is also saved in each history. A decrease after epoch {protocol['candidate_epochs']} is descriptive evidence of late validation improvement. Grokking requires a demonstrated memorization phase followed by delayed generalization; double descent requires a reproducible rise and subsequent fall around an interpolation regime. Neither is inferred automatically from a long run or a visually noisy curve. The references concern particular experimental settings and do not guarantee either phenomenon on reconstructed wildfire labels.","",
                  "[Grokking paper](https://arxiv.org/abs/2201.02177) and [Deep Double Descent paper](https://arxiv.org/abs/1912.02292).", ""]
        for family,d in diagnostics.items():
            lines.append(f"- {family}: best validation Brier through epoch {protocol['candidate_epochs']}={d['best_first_stage_validation_brier']:.6f}; after epoch {protocol['candidate_epochs']}={fmt(d['best_late_validation_brier'])}; selected epoch={d['best_epoch']}; minimum matched training Brier={d['minimum_training_brier']:.6f}.")
        lines += ["", "## Saved artifacts and limits", "", "`protocol.json` binds all input cache hashes, source hashes and the prespecified search. `candidate_selection.json`, `finalist_selection.json` and `selection.json` record validation-only selection. Candidate folders contain the complete per-epoch histories, selected public checkpoints and resumable final optimizer/RNG states. `predictions/` retains probabilities for all base rows and matched identities/weights. `metrics.json` retains calibration, exact and clipped NLL, Bernoulli distances, KL, AP, PR AUC, F1 and MCC. Classification thresholds are selected independently on native and matched validation populations.","",
                  "The training labels are retrospective reconstructions. Scores are inverse-inclusion-weighted sampled estimates, not exact full-grid population scores. No active-flame residence assumption was introduced. The search uses one seed and does not establish robustness, a globally best parameter setting, double descent, or grokking.", ""]
        if protocol.get("smoke_verification_only"):
            lines[2:2] = ["**EXECUTION VERIFICATION ONLY.** This short run uses a small sampled subset of the real cache and reduced epoch/tree budgets. Its numerical scores verify the pipeline and must not be used as scientific model rankings, population estimates, or evidence of grokking/double descent.", ""]
        (output/"report.md").write_text("\n".join(lines))
        fields=sorted(set().union(*(r.keys() for r in csv_rows)))
        with (output/"metrics.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(csv_rows)


    @staticmethod
    def run_all(args):
        Search.train_search(args)
        Search.forest_search(args)
        Search.finalize(args)


    @staticmethod
    def smoke(args):
        """Run every family/stage on real cache subsets with a short epoch budget."""
        source=args.cache
        if args.output==Search.DEFAULT_OUTPUT:args.output=Search.DEFAULT_SMOKE_OUTPUT
        destination=args.output/"smoke_cache"
        if not destination.exists():
            metadata=json.loads((source/"metadata.json").read_text())
            destination.mkdir(parents=True)
            rng=np.random.default_rng(args.seed)
            sampling={}
            for split in ("train","validation","test"):
                data=Search.load_split(source,split,metadata)
                count=512 if split=="train" else 256
                c3=data.burned[:,:,3:6,3:6].sum((1,2,3))>0
                c9=data.neighbor_count>0
                groups=[c3 & (data.target==label) for label in (0,1)] + [~c9 & (data.target==label) for label in (0,1)]
                indices=[]
                for mask in groups:
                    candidates=np.flatnonzero(mask)
                    indices.extend(rng.choice(candidates,min(32,len(candidates)),replace=False).tolist())
                remaining=np.setdiff1d(np.arange(len(data)),indices)
                indices=np.sort(np.r_[indices,rng.choice(remaining,count-len(indices),replace=False)]).astype(np.int64)
                payload={key:getattr(data,key)[indices] for key in CachedSplit.__dataclass_fields__}
                np.savez_compressed(destination/f"{split}.npz",**payload,original_base_index=indices)
                sampling[split]=dict(base_rows=len(data),smoke_rows=count,seed=args.seed)
            metadata.update(smoke_verification_only=True,smoke_original_cache=str(source.resolve()),smoke_sampling=sampling)
            write_json(destination/"metadata.json",metadata)
        args.cache=destination;args.epochs=2;args.finalist_epochs=4;args.forest_trees=9
        Search.run_all(args)


    @staticmethod
    def parser():
        p=argparse.ArgumentParser(description=Search.__doc__)
        p.add_argument("stage",choices=("run","smoke","train","forests","finalize"))
        p.add_argument("--cache",type=Path,default=Search.DEFAULT_CACHE)
        p.add_argument("--output",type=Path,default=Search.DEFAULT_OUTPUT)
        p.add_argument("--epochs",type=int,default=512)
        p.add_argument("--finalist-epochs",type=int,default=4096)
        p.add_argument("--seed",type=int,default=7)
        add_categorical_balance_arguments(p)
        p.add_argument("--threads",type=int,default=4)
        p.add_argument("--forest-trees",type=int,default=100)
        p.add_argument("--device",default="auto",help="auto chooses MPS, then CUDA, then CPU; resume requires same training device")
        return p


    @staticmethod
    def main():
        args=Search.parser().parse_args()
        if args.device=="auto":args.device="mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        if args.epochs<1 or args.finalist_epochs<args.epochs or args.threads<1:
            raise ValueError("Epochs/threads must be positive and finalist budget must include initial training")
        {"run":Search.run_all,"smoke":Search.smoke,"train":Search.train_search,"forests":Search.forest_search,"finalize":Search.finalize}[args.stage](args)


class ScheduledSearch:
    """Fresh nonnegative kernel searches crossing peak rates and fixed schedules.

    The declared partitions, labels and inverse sampling weights come from one
    frozen 9x9 cache. Each model trains on its K-contact rows. Hyperparameters,
    epochs, finalists and classification thresholds use validation only. Final
    test predictions cover every base-cache row; comparison metrics use native
    K-contact and identical 3-contact cohorts. No early stopping is used.
    """

    __doc__ = __doc__.replace("\n    ", "\n")
    __file__ = __file__
    split_contract_fields = staticmethod(Search.split_contract_fields)
    split_description = staticmethod(Search.split_description)
    fit_native_balance = staticmethod(Search.fit_native_balance)
    bind_tensor_balance = staticmethod(Search.bind_tensor_balance)
    balance_description = staticmethod(Search.balance_description)
    validate_categorical_normalization = staticmethod(Search.validate_categorical_normalization)
    verify_balance_reports = staticmethod(Search.verify_balance_reports)
    verify_checkpoint_balance = staticmethod(Search.verify_checkpoint_balance)
    PatchRandomForest = staticmethod(PatchRandomForest)
    brier = staticmethod(brier)
    probability_metrics_with_all = staticmethod(probability_metrics_with_all)
    balance_settings_from_args = staticmethod(balance_settings_from_args)
    load_split = staticmethod(load_split)
    load_trained_model = staticmethod(load_single_trained_model)
    TRAINING_SOURCE_FILES = CANONICAL_TRAINING_SOURCE_FILES

    RUNS = PATH_RUNS
    DEFAULT_CACHE = RUNS / "20261009_weighted_stratified_split/prepared_all"
    DEFAULT_OUTPUT = RUNS / "20261009_scheduled_learning_rate_search_weighted_stratified_categorical_balanced"
    DEFAULT_SMOKE_OUTPUT = RUNS / "20261009_scheduled_learning_rate_smoke_weighted_stratified_categorical_balanced"
    DEFAULT_LEARNING_RATES = (.001, .003, .01, .03)
    DEFAULT_SCHEDULES = ("constant", "warmup_cosine")
    SIZES = (3, 5, 7, 9)
    NEURAL_FAMILIES = ("legacy", "cnn", "mlp", "residual_mlp")


    @staticmethod
    def sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


    @staticmethod
    def candidate_plan(learning_rates=DEFAULT_LEARNING_RATES, schedules=DEFAULT_SCHEDULES,
                       horizon=4096, warmup_epochs=32, minimum_lr_factor=.01, restart_period=512):
        """Cross ten architecture/regularization settings with rates and schedules.

        For each kernel/architecture setting, every variant receives the same seed,
        initialization, training cohort, normalization, dropout, and weight decay.
        This is a full rate-by-schedule crossing over a joint architecture search.
        """
        learning_rates = tuple(float(value) for value in learning_rates)
        schedules = tuple(schedules)
        if not learning_rates or len(set(learning_rates)) != len(learning_rates):
            raise ValueError("Learning rates must be a nonempty list without duplicates")
        if any(not math.isfinite(rate) or rate <= 0 for rate in learning_rates):
            raise ValueError("Learning rates must be finite and positive")
        if not schedules or len(set(schedules)) != len(schedules):
            raise ValueError("Schedules must be a nonempty list without duplicates")
        scheduler_configurations = [validate_scheduler(dict(name=name, horizon=horizon, warmup_epochs=warmup_epochs,
                                                           minimum_lr_factor=minimum_lr_factor, restart_period=restart_period))
                                    for name in schedules]
        configurations = [
            ("constant", 1, 1, 0., .01, 0.),
            ("linear", 1, 1, 0., .01, .0001),
            ("legacy", 16, 1, 0., .001, .0001),
            ("cnn", 32, 1, .15, .003, .001),
            ("mlp", 8, 2, 0., .003, 0.),
            ("mlp", 32, 2, .15, .003, .0001),
            ("mlp", 128, 2, .15, .003, .01),
            ("mlp", 32, 4, 0., .001, .1),
            ("residual_mlp", 32, 3, .15, .003, .001),
            ("residual_mlp", 128, 3, .15, .001, .01),
        ]
        plan = []
        for k in ScheduledSearch.SIZES:
            for index, (family, width, depth, dropout, _, decay) in enumerate(configurations):
                base_id = f"k{k}_{family}_{index:02d}"
                for rate in learning_rates:
                    for scheduler in scheduler_configurations:
                        plan.append(dict(id=f"{base_id}_lr{rate!r}_{scheduler['name']}",
                                         base_configuration_id=base_id, kernel_size=k, family=family,
                                         hidden_channels=width, depth=depth, dropout=dropout,
                                         learning_rate=rate, weight_decay=decay, scheduler=dict(scheduler)))
        return plan


    @staticmethod
    def verify_protocol(protocol, cache):
        """Reject input/code drift before resuming or exposing test outcomes."""
        if str(cache.resolve()) != protocol["cache"]:
            raise ValueError("Cache path differs from the frozen experiment protocol")
        for name, expected in protocol["cache_sha256"].items():
            if ScheduledSearch.sha256(cache / name) != expected:
                raise ValueError(f"Cache integrity mismatch: {name}; use a new output directory for changed inputs")
        for name, expected in protocol["training_source_sha256"].items():
            if not (Path(__file__).parent / name).is_file() or ScheduledSearch.sha256(Path(__file__).parent / name) != expected:
                raise ValueError(f"Training source integrity mismatch: {name}; use a new output directory for changed code")


    @staticmethod
    def setup(output, cache, epochs, finalist_epochs, seed, forest_trees=100, *,
              learning_rates=DEFAULT_LEARNING_RATES, schedules=DEFAULT_SCHEDULES,
              warmup_epochs=32, minimum_lr_factor=.01, restart_period=512, balance_settings=None):
        balance_settings = validate_categorical_balance_settings(**(balance_settings or {}))
        if epochs < 1 or finalist_epochs < epochs:
            raise ValueError("Candidate epochs must be positive and fit inside the finalist horizon")
        candidates = ScheduledSearch.candidate_plan(learning_rates, schedules, finalist_epochs, warmup_epochs,
                                    minimum_lr_factor, restart_period)
        settings = dict(learning_rates=[float(v) for v in learning_rates], schedules=list(schedules),
                        scheduling_horizon=finalist_epochs, warmup_epochs=warmup_epochs,
                        minimum_lr_factor=float(minimum_lr_factor), restart_period=restart_period,
                        categorical_balance_settings=balance_settings)
        output.mkdir(parents=True, exist_ok=True)
        path = output / "protocol.json"
        if path.exists():
            protocol = json.loads(path.read_text())
            for key, value in {"cache": str(cache.resolve()), "candidate_epochs": epochs,
                               "finalist_epochs": finalist_epochs, "seed": seed, "forest_trees": forest_trees,
                               **settings, "candidates": candidates}.items():
                if protocol[key] != value:
                    raise ValueError(f"Resume protocol mismatch: {key}")
            ScheduledSearch.verify_protocol(protocol, cache)
            return protocol
        metadata = json.loads((cache / "metadata.json").read_text())
        validate_split_metadata(metadata, require_all_partitions=True)
        if metadata["dt_hours"] != 1. or metadata["kernel_size"] != 9:
            raise ValueError("The experiment requires the frozen one-hour 9x9 base cache")
        hashes = {name: ScheduledSearch.sha256(cache / name) for name in ("metadata.json", "train.npz", "validation.npz", "test.npz")}
        source_checks = []
        root = resolve_source_root(metadata)
        for source in metadata.get("source_files", []):
            actual = root / source["path"]
            if not actual.is_file() or ScheduledSearch.sha256(actual) != source["sha256"]:
                raise ValueError(f"Source integrity mismatch: {actual}")
            source_checks.append(source["path"])
        sources = {name: ScheduledSearch.sha256(Path(__file__).parent / name) for name in ScheduledSearch.TRAINING_SOURCE_FILES}
        protocol = dict(cache=str(cache.resolve()), candidate_epochs=epochs, finalist_epochs=finalist_epochs,
                        seed=seed, forest_trees=forest_trees, kernel_sizes=list(ScheduledSearch.SIZES), candidates=candidates, **settings,
                        training="Native K-contact cells from one frozen base sampling design; complete known context; current center unburned",
                        contact="At least one off-center cell already burned at time t inside centered KxK; cumulative reconstructed burned map, not active flame",
                        common="Identical original 9x9 cache rows with contact inside centered 3x3; original labels and inverse inclusion weights",
                        selection="Minimum float64 inverse-weighted common-contact validation Brier; checkpoint and hyperparameters before test",
                        long_finalists="One globally validation-selected candidate per neural family (legacy, cnn, mlp, residual_mlp), continued from last optimizer state to the full finalist epoch budget",
                        optimizer="AdamW, full-batch categorical optimization-weighted Brier/optimization prevalence, explicit prespecified rate before every optimizer step, decay on all parameters, no early stopping",
                        schedule="One-based optimizer steps; the full finalist horizon is fixed from step one, including candidates initially trained only to the candidate budget; no validation-triggered scheduling",
                        controlled_comparison="Peak rate and schedule crossed within each fixed kernel/architecture/regularization configuration, sharing initialization and seed; compare first-stage validation trajectories at identical epoch budgets",
                        weight_decay_interpretation="AdamW decay multiplies each parameter by (1-learning_rate*weight_decay) per optimizer step; equal nominal decay with different schedules does not imply equal integrated shrinkage",
                        prediction="All original base-cache rows, including no-contact inputs; neural kernel structural zero for known no-contact",
                        test_used_for_selection=False, cache_sha256=hashes, training_source_sha256=sources,
                        verified_source_files=len(source_checks), target="unburned at t becomes burned at exactly t+3600s",
                        limitations=["Retrospective reconstructed hourly labels; not independent observed active flames",
                                     "Best among the finite prespecified joint configurations; not a global optimum",
                                     "Four single-seed neural finalists; curves can suggest delayed generalization, not prove grokking or double descent"],
                        versions=dict(python=platform.python_version(), numpy=np.__version__, torch=str(torch.__version__)),
                        references=["https://arxiv.org/abs/2201.02177", "https://arxiv.org/abs/1912.02292"])
        protocol.update(ScheduledSearch.split_contract_fields(metadata))
        protocol["training"] += "; split unit: " + protocol["split_unit"]
        protocol["smoke_verification_only"] = bool(metadata.get("smoke_verification_only", False))
        snapshot = output / "source_snapshot"
        snapshot.mkdir(exist_ok=True)
        for name in sources:
            (snapshot / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(__file__).parent / name, snapshot / name)
        write_json(path, protocol)
        return protocol


    @staticmethod
    def build(candidate, channels, device):
        if candidate["family"] == "legacy":
            model = EnvironmentConditionedConvolution(channels, candidate["kernel_size"], candidate["hidden_channels"])
        else:
            model = build_kernel_model(channels, candidate["kernel_size"], candidate["family"],
                                       candidate["hidden_channels"], candidate["depth"], candidate["dropout"])
        return model.to(device)


    @staticmethod
    def _pointwise(layer, value):
        """Exact affine/activation computation at one spatial output position."""
        if isinstance(layer, nn.Conv2d):
            return F.linear(value, layer.weight.flatten(1), layer.bias)
        if isinstance(layer, nn.Dropout2d):
            # At spatial shape 1x1, channel dropout equals scalar feature dropout.
            return F.dropout(value, layer.p, layer.training)
        if isinstance(layer, nn.Sequential):
            for member in layer:
                value = ScheduledSearch._pointwise(member, value)
            return value
        if hasattr(layer, "update"):
            return F.silu(value + ScheduledSearch._pointwise(layer.update, value))
        return layer(value)


    @staticmethod
    def cached_probability(model, features, burned):
        """Trusted validated feature path retaining the public model's parameters.

        Linear rather than 1x1 convolution avoids repeated GPU validation barriers.
        The full spatial first layer is a flattened dot product. CPU float64 and
        device float32 equivalence are checked before and after every fitted run.
        Dropout has the same law at the single output position.
        """
        network = model.kernel_network
        if isinstance(network, nn.Sequential):
            logits = ScheduledSearch._pointwise(network, features)
        elif hasattr(network, "logits"):
            logits = network.logits.reshape(1, -1).expand(len(features), -1)
        else:
            hidden = F.linear(features, network.spatial.weight.flatten(1), network.spatial.bias)
            logits = ScheduledSearch._pointwise(network.output, ScheduledSearch._pointwise(network.hidden, hidden))
        rate = (F.softplus(logits) * burned).sum(dim=1)
        return -torch.expm1(-rate)


    @dataclass
    class TensorData:
        features: torch.Tensor
        burned: torch.Tensor
        target: np.ndarray
        weight: np.ndarray
        target_tensor: torch.Tensor
        loss_weight: torch.Tensor
        common: np.ndarray
        optimization_weight: np.ndarray | None = None
        categorical_balance: dict | None = None


    @staticmethod
    def tensor_data(data, mean, std, family, device, common=None, *,
                    optimization_weight=None, categorical_balance=None):
        n = len(data)
        spatial = family in ("legacy", "cnn")
        shape = (n, data.environment.shape[1] * data.environment.shape[-1] ** 2) if spatial else (n, data.environment.shape[1])
        features = np.empty(shape, dtype=np.float32)
        for start in range(0, n, 4096):
            end = min(start + 4096, n)
            normalized = (data.environment[start:end] - mean[None, :, None, None]) / std[None, :, None, None]
            features[start:end] = normalized.reshape(end-start, -1) if spatial else normalized.mean(axis=(2, 3))
        burned = data.burned.reshape(n, -1).copy()
        burned[:, burned.shape[1] // 2] = 0.
        effective = np.asarray(data.weight if optimization_weight is None else optimization_weight, dtype=np.float64)
        if effective.shape != (n,) or not np.isfinite(effective).all() or not (effective > 0).all():
            raise ValueError("Optimization weights must be positive finite values aligned with training rows")
        weights = (effective / effective.mean()).astype(np.float32)
        return ScheduledSearch.TensorData(torch.from_numpy(features).to(device), torch.from_numpy(burned).to(device),
                          data.target, data.weight, torch.from_numpy(data.target).to(device),
                          torch.from_numpy(weights).to(device), np.arange(n) if common is None else common,
                          effective, categorical_balance)


    @staticmethod
    @torch.no_grad()
    def probabilities(model, tensors, batch_size=65536):
        model.eval()
        output = np.empty(len(tensors.target), dtype=np.float32)
        for start in range(0, len(output), batch_size):
            end = min(start+batch_size, len(output))
            output[start:end] = ScheduledSearch.cached_probability(model, tensors.features[start:end], tensors.burned[start:end]).cpu().numpy()
        if not np.isfinite(output).all() or not ((output >= 0) & (output <= 1)).all():
            raise RuntimeError("Nonfinite or out-of-range kernel predictions")
        return output


    @staticmethod
    @torch.no_grad()
    def verify_equivalence(model, data, mean, std, family, device):
        small = crop_split(data, model.kernel_size, np.arange(min(8, len(data))))
        env = torch.from_numpy(small.environment.copy()).to(device)
        env = (env - torch.tensor(mean, device=device)[None,:,None,None]) / torch.tensor(std, device=device)[None,:,None,None]
        burned = torch.from_numpy(small.burned.copy()).to(device)
        model.eval()
        features = env.flatten(1) if family in ("legacy", "cnn") else env.mean((2,3))
        cached = ScheduledSearch.cached_probability(model, features, burned.flatten(1))
        public_center = center_probability(model, env, burned)
        c = model.kernel_size // 2
        grid_center = model(burned, env).probability[:,0,c,c]
        device_error = float(torch.max(torch.abs(cached-grid_center)).cpu())
        if not torch.allclose(cached, public_center, atol=2e-6, rtol=2e-5) or not torch.allclose(cached, grid_center, atol=2e-6, rtol=2e-5):
            raise AssertionError(f"Cached/public model mismatch: {device_error}")
        reference = copy.deepcopy(model).cpu().double().eval()
        x, b = env.cpu().double(), burned.cpu().double()
        f = x.flatten(1) if family in ("legacy", "cnn") else x.mean((2,3))
        exact = ScheduledSearch.cached_probability(reference, f, b.flatten(1))
        grid = reference(b,x).probability[:,0,c,c]
        error = float((exact-grid).abs().max())
        if not torch.allclose(exact, grid, atol=1e-12, rtol=1e-12):
            raise AssertionError(f"Float64 cached/public model mismatch: {error}")
        return dict(device_float32_max_error=device_error, cpu_float64_max_error=error)


    @staticmethod
    def make_contract(candidate, metadata, protocol):
        k = candidate["kernel_size"]
        contract = dict(format_version=1, architecture="EnvironmentConditionedConvolution" if candidate["family"]=="legacy" else "LearnedNonnegativeKernel",
                        in_channels=len(metadata["channels"]), channels=metadata["channels"], kernel_size=k,
                        hidden_channels=candidate["hidden_channels"], dt_hours=1., center_rate=0.,
                        eligibility="at_least_one_burned_neighbor", target=protocol["target"],
                        kernel_constraint="nonnegative", output_link="one_hour_exponential", evaluation_grouping="pooled_countries",
                        population_condition=f"Known currently unburned target with complete K={k} context and at least one already-burned neighbor",
                        normalization="Continuous channels use training-only native K-contact population-weighted moments; one-hot channels retain raw 0/1 with mean=0 and scale=1",
                        event_ids=metadata["event_ids"], splits=metadata["splits"],
                        cache_metadata_sha256=protocol["cache_sha256"]["metadata.json"])
        if candidate["family"] != "legacy":
            contract["kernel_model"] = {"architecture":candidate["family"], "hidden_channels":candidate["hidden_channels"],
                                       "depth":candidate["depth"], "dropout":candidate["dropout"]}
        contract["categorical_balance_settings"] = protocol.get("categorical_balance_settings", validate_categorical_balance_settings())
        contract.update(ScheduledSearch.split_contract_fields(metadata))
        contract.update({key:metadata[key] for key in SCHEMA_KEYS if key in metadata})
        return contract


    @staticmethod
    def parameter_sha256(model):
        """Hash ordered parameter values to verify paired variant initialization."""
        digest = hashlib.sha256()
        for name, value in model.state_dict().items():
            array = value.detach().cpu().contiguous().numpy()
            digest.update(name.encode("utf-8"))
            digest.update(str(array.dtype).encode("ascii"))
            digest.update(str(array.shape).encode("ascii"))
            digest.update(array.tobytes())
        return digest.hexdigest()


    @staticmethod
    def fit_candidate(candidate, train_data, validation_data, tensors, validation_tensors,
                      mean, std, global_baseline, metadata, protocol, output, device, epochs):
        scheduler = validate_scheduler(candidate["scheduler"])
        if scheduler["horizon"] != protocol["finalist_epochs"]:
            raise ValueError("Candidate scheduling horizon must equal the frozen finalist epoch budget")
        if not 1 <= epochs <= scheduler["horizon"]:
            raise ValueError("Training endpoint must lie inside the frozen scheduling horizon")
        ScheduledSearch.validate_categorical_normalization(mean, std, metadata)
        balance_audit = ScheduledSearch.bind_tensor_balance(train_data, metadata, protocol, output, tensors, device)
        folder = output / "candidates" / candidate["id"]
        folder.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(protocol["seed"])
        if device.type == "mps":
            torch.mps.manual_seed(protocol["seed"])
        model = ScheduledSearch.build(candidate, len(metadata["channels"]), device)
        initialize_kernel_rate(model, max(global_baseline["per_neighbor_rate_per_hour"], 1e-8))
        initial_parameter_sha256 = ScheduledSearch.parameter_sha256(model)
        optimizer = torch.optim.AdamW(model.parameters(), lr=candidate["learning_rate"], weight_decay=candidate["weight_decay"])
        history_path, last_path = folder / "history.json", folder / "last.pt"
        history = []
        best_score = math.inf
        if last_path.exists():
            saved = torch.load(last_path, map_location=device, weights_only=True)
            if saved.get("candidate") != candidate or saved.get("device") != str(device):
                raise ValueError("Resume requires the same candidate configuration and training device")
            if saved.get("categorical_balance") != balance_audit:
                raise ValueError("Resume categorical balancing differs from the committed optimization weights")
            if saved.get("initial_parameter_sha256") != initial_parameter_sha256:
                raise ValueError("Fresh seeded initialization differs from the resumable candidate")
            model.load_state_dict(saved["model_state_dict"])
            optimizer.load_state_dict(saved["optimizer_state_dict"])
            history = json.loads(history_path.read_text())[:saved["epoch"]]
            if len(history) != saved["epoch"] or any(
                    row.get("optimizer_step") != index or row.get("learning_rate") != learning_rate_at_step(candidate["learning_rate"], index, scheduler)
                    for index, row in enumerate(history, 1)):
                raise ValueError("Resume history differs from the committed learning-rate trajectory")
            best_score = saved["best_validation_brier"]
            # Recover the last committed best checkpoint even if interruption
            # occurred between a subsequent best save and the next state snapshot.
            torch.save(saved["best_checkpoint"], folder / "checkpoint.pt")
            torch.set_rng_state(saved["cpu_rng_state"].cpu())
            if device.type == "mps":
                torch.mps.set_rng_state(saved["mps_rng_state"].cpu())
            if device.type == "cuda":
                torch.cuda.set_rng_state_all([s.cpu() for s in saved["cuda_rng_states"]])
        contract = ScheduledSearch.make_contract(candidate, metadata, protocol)
        contract["categorical_balance"] = balance_audit
        verification = ScheduledSearch.verify_equivalence(model, train_data, mean, std, candidate["family"], device)
        prevalence = float(np.sum(train_data.weight*train_data.target)/np.sum(train_data.weight))
        optimization_prevalence = float(np.dot(tensors.optimization_weight, train_data.target) / tensors.optimization_weight.sum())
        if not 0 < optimization_prevalence < 1:
            raise ValueError("Optimization requires positive and negative native training targets")
        started = time.perf_counter()
        start_epoch = len(history)
        for epoch in range(start_epoch+1, epochs+1):
            learning_rate = learning_rate_at_step(candidate["learning_rate"], epoch, scheduler)
            for parameter_group in optimizer.param_groups:
                parameter_group["lr"] = learning_rate
            model.train()
            optimizer.zero_grad(set_to_none=True)
            # Chunked backward implements ONE full-batch optimizer step per epoch.
            # It reduces activation memory while retaining the fitted categorical optimization weights.
            loss_value = 0.
            n = len(train_data)
            for start in range(0,n,65536):
                end = min(start+65536,n)
                p = ScheduledSearch.cached_probability(model,tensors.features[start:end],tensors.burned[start:end])
                loss = (tensors.loss_weight[start:end]*(p-tensors.target_tensor[start:end]).square()).sum()/(n*optimization_prevalence)
                loss.backward()
                loss_value += float(loss.detach().cpu())
            gradient_norm = nn.utils.clip_grad_norm_(model.parameters(), max_norm=10., error_if_nonfinite=True)
            optimizer.step()
            p_train, p_val = ScheduledSearch.probabilities(model,tensors), ScheduledSearch.probabilities(model,validation_tensors)
            train_brier = brier(train_data.target,p_train,train_data.weight)
            optimization_train_brier = brier(train_data.target,p_train,tensors.optimization_weight)
            tc = tensors.common
            train_common_brier = brier(train_data.target[tc],p_train[tc],train_data.weight[tc])
            native_brier = brier(validation_data.target,p_val,validation_data.weight)
            ci = validation_tensors.common
            common_brier = brier(validation_data.target[ci],p_val[ci],validation_data.weight[ci])
            improved = common_brier < best_score
            if improved:
                best_score = common_brier
                checkpoint = dict(contract=contract,model_state_dict=model.state_dict(), normalization_mean=torch.from_numpy(mean.copy()),
                                  normalization_std=torch.from_numpy(std.copy()),best_epoch=epoch,validation_brier=best_score,
                                  configuration=candidate,global_rate_baseline=global_baseline,train_weighted_prevalence=prevalence,
                                  optimization_weighted_prevalence=optimization_prevalence,
                                  initial_parameter_sha256=initial_parameter_sha256,optimizer_step=epoch,learning_rate=learning_rate)
                torch.save(checkpoint,folder/"checkpoint.pt")
            record = dict(epoch=epoch,optimizer_step=epoch,learning_rate=learning_rate,
                          train_brier=train_brier,train_common_brier=train_common_brier,validation_native_brier=native_brier,
                          validation_common_brier=common_brier,training_regularized_dropout_loss=loss_value,
                          optimization_weighted_prevalence=optimization_prevalence,population_weighted_prevalence=prevalence,
                          optimization_train_brier=optimization_train_brier,
                          gradient_norm=float(gradient_norm.cpu()),parameter_norm=math.sqrt(sum(float(p.detach().square().sum().cpu()) for p in model.parameters())),
                          selected=improved,elapsed_seconds=time.perf_counter()-started)
            history.append(record)
            if epoch%32==0 or epoch==epochs:
                write_json(history_path,history)
                state = dict(model_state_dict=model.state_dict(),optimizer_state_dict=optimizer.state_dict(),epoch=epoch,
                             best_validation_brier=best_score,cpu_rng_state=torch.get_rng_state(),candidate=candidate,device=str(device),
                             categorical_balance=balance_audit,
                             initial_parameter_sha256=initial_parameter_sha256,scheduler=scheduler,next_optimizer_step=epoch+1,
                             best_checkpoint=torch.load(folder/"checkpoint.pt", map_location="cpu", weights_only=True))
                if device.type=="mps":state["mps_rng_state"]=torch.mps.get_rng_state()
                if device.type=="cuda":state["cuda_rng_states"]=torch.cuda.get_rng_state_all()
                torch.save(state,last_path)
                print(f"{candidate['id']} epoch={epoch}/{epochs} train={train_brier:.7f} val_common={common_brier:.7f} best={best_score:.7f}",flush=True)
        selected = torch.load(folder/"checkpoint.pt",map_location=device,weights_only=True)
        model.load_state_dict(selected["model_state_dict"])
        verification["selected_checkpoint"] = ScheduledSearch.verify_equivalence(model,train_data,mean,std,candidate["family"],device)
        reloaded = ScheduledSearch.load_trained_model(folder/"checkpoint.pt",device)
        if not all(torch.equal(a,b) for a,b in zip(model.state_dict().values(),reloaded.model.state_dict().values())):
            raise AssertionError("Checkpoint parameters changed on public reload")
        summary = dict(candidate=candidate,epochs_completed=len(history),best_epoch=selected["best_epoch"],
                       validation_common_brier=best_score,checkpoint=str((folder/"checkpoint.pt").resolve()),
                       train_sample_count=len(train_data),validation_native_sample_count=len(validation_data),
                       validation_common_sample_count=len(validation_tensors.common),early_stopped=False,
                       checkpoint_sha256=ScheduledSearch.sha256(folder/"checkpoint.pt"),
                       trainable_parameters=sum(p.numel() for p in model.parameters()),verification=verification,
                       test_used_for_selection=False,device=str(device),initial_parameter_sha256=initial_parameter_sha256,
                       categorical_balance=balance_audit,population_weighted_prevalence=prevalence,
                       optimization_weighted_prevalence=optimization_prevalence,
                       final_learning_rate=history[-1]["learning_rate"],scheduling_horizon=scheduler["horizon"])
        write_json(folder/"summary.json",summary)
        return summary


    @staticmethod
    def setup_from_args(args):
        return ScheduledSearch.setup(args.output,args.cache,args.epochs,args.finalist_epochs,args.seed,args.forest_trees,
                     learning_rates=args.learning_rates,schedules=args.schedules,warmup_epochs=args.warmup_epochs,
                     minimum_lr_factor=args.minimum_lr_factor,restart_period=args.restart_period,
                     balance_settings=balance_settings_from_args(args))


    @staticmethod
    def train_search(args):
        protocol = ScheduledSearch.setup_from_args(args)
        metadata = json.loads((args.cache/"metadata.json").read_text())
        train_base, validation_base = (ScheduledSearch.load_split(args.cache,name,metadata) for name in ("train","validation"))
        validate_partition_disjointness({"train": train_base, "validation": validation_base}, metadata)
        device = choose_device(args.device)
        torch.set_num_threads(args.threads)
        summaries = []
        balance_by_k = {}
        for k in ScheduledSearch.SIZES:
            ti,vi = native_indices(train_base,k),native_indices(validation_base,k)
            train_data, val_data = crop_split(train_base,k,ti),crop_split(validation_base,k,vi)
            balance_by_k[k] = ScheduledSearch.fit_native_balance(train_data, metadata, protocol, args.output)
            effective, balance_audit = balance_by_k[k]
            mean,std = fit_normalization(train_data, metadata=metadata)
            global_baseline = fit_global_rate(train_data)
            tci = np.flatnonzero(np.isin(ti,common_indices(train_base)))
            ci = np.flatnonzero(np.isin(vi,common_indices(validation_base)))
            for spatial in (False,True):
                family = "legacy" if spatial else "mlp"
                tensors, vt = ScheduledSearch.tensor_data(train_data,mean,std,family,device,tci,optimization_weight=effective,categorical_balance=balance_audit),ScheduledSearch.tensor_data(val_data,mean,std,family,device,ci)
                for candidate in [c for c in protocol["candidates"] if c["kernel_size"]==k and ((c["family"] in ("legacy","cnn"))==spatial)]:
                    summary_path=args.output/"candidates"/candidate["id"]/"summary.json"
                    if summary_path.exists() and json.loads(summary_path.read_text())["epochs_completed"]>=args.epochs:
                        existing = json.loads(summary_path.read_text())
                        if existing["candidate"] != candidate or existing["device"] != str(device):
                            raise ValueError("Resume requires the same candidate configuration and training device")
                        if existing.get("categorical_balance") != balance_audit:
                            raise ValueError("Resume categorical balancing differs from the native training cohort")
                        summaries.append(existing)
                    else:
                        summaries.append(ScheduledSearch.fit_candidate(candidate,train_data,val_data,tensors,vt,mean,std,global_baseline,metadata,protocol,args.output,device,args.epochs))
                    write_json(args.output/"candidate_selection.json",summaries)
                del tensors,vt
                if device.type=="mps":torch.mps.empty_cache()
            del train_data,val_data
        frozen_finalists=args.output/"finalist_selection.json"
        if frozen_finalists.exists():
            before_extension=json.loads(frozen_finalists.read_text())["selection_before_extension"]
            candidates_by_id={s["candidate"]["id"]:s for s in summaries}
            finalists=[candidates_by_id[s["candidate"]["id"]] for s in before_extension]
        else:
            finalists = [min((s for s in summaries if s["candidate"]["family"]==family),key=lambda s:s["validation_common_brier"]) for family in ScheduledSearch.NEURAL_FAMILIES]
            write_json(frozen_finalists,dict(selection_before_extension=finalists,test_used_for_selection=False))
        for selected in finalists:
            c=selected["candidate"];k=c["kernel_size"]
            ti,vi=native_indices(train_base,k),native_indices(validation_base,k)
            td,vd=crop_split(train_base,k,ti),crop_split(validation_base,k,vi)
            effective, balance_audit = balance_by_k[k]
            mean,std=fit_normalization(td, metadata=metadata);baseline=fit_global_rate(td)
            ci=np.flatnonzero(np.isin(vi,common_indices(validation_base)))
            tci=np.flatnonzero(np.isin(ti,common_indices(train_base)))
            tensors,vt=ScheduledSearch.tensor_data(td,mean,std,c["family"],device,tci,optimization_weight=effective,categorical_balance=balance_audit),ScheduledSearch.tensor_data(vd,mean,std,c["family"],device,ci)
            extended=ScheduledSearch.fit_candidate(c,td,vd,tensors,vt,mean,std,baseline,metadata,protocol,args.output,device,args.finalist_epochs)
            summaries=[extended if s["candidate"]["id"]==c["id"] else s for s in summaries]
            write_json(args.output/"candidate_selection.json",summaries)
            del tensors,vt,td,vd
            if device.type=="mps":torch.mps.empty_cache()
        write_json(args.output/"neural_complete.json",dict(completed=True,candidates=len(summaries),long_finalists=len(finalists),test_used_for_selection=False))
        ScheduledSearch.write_learning_rate_comparisons(args.output, protocol, summaries)


    @staticmethod
    def write_learning_rate_comparisons(output, protocol, summaries):
        """Compare rates/schedules at the same first-stage budget and seeded start.

        A continued finalist's later validation outcomes are excluded from this
        comparison so they cannot acquire an unequal 4,096-versus-512 advantage.
        Final model selection can still use the entire authorized trajectory.
        """
        rows = []
        initial_hashes = {}
        for summary in summaries:
            candidate = summary["candidate"]
            base = candidate["base_configuration_id"]
            hashes = initial_hashes.setdefault(base, set())
            hashes.add(summary["initial_parameter_sha256"])
            if len(hashes) != 1:
                raise AssertionError(f"Rate/schedule variants have different initial parameters: {base}")
            history = json.loads((output/"candidates"/candidate["id"]/"history.json").read_text())
            first = history[:protocol["candidate_epochs"]]
            if len(first) != protocol["candidate_epochs"]:
                raise ValueError(f"Incomplete first-stage history: {candidate['id']}")
            best = min(first, key=lambda r: r["validation_common_brier"])
            rows.append(dict(base_configuration_id=base,candidate_id=candidate["id"],family=candidate["family"],
                             kernel_size=candidate["kernel_size"],hidden_channels=candidate["hidden_channels"],
                             depth=candidate["depth"],dropout=candidate["dropout"],weight_decay=candidate["weight_decay"],
                             peak_learning_rate=candidate["learning_rate"],schedule=candidate["scheduler"]["name"],
                             compared_epochs=len(first),best_epoch=best["epoch"],
                             validation_common_brier=best["validation_common_brier"],
                             final_validation_common_brier=first[-1]["validation_common_brier"],
                             final_train_common_brier=first[-1]["train_common_brier"],
                             final_learning_rate=first[-1]["learning_rate"],
                             initial_parameter_sha256=summary["initial_parameter_sha256"],test_used_for_selection=False))
        write_json(output/"learning_rate_comparison.json",dict(compared_epochs=protocol["candidate_epochs"],
                   interpretation="Validation-only matched first-stage budgets and identical initialization within each architecture/kernel/regularization setting; nominal AdamW decay is fixed but integrated shrinkage changes with rate trajectory",
                   test_used_for_selection=False,rows=rows))
        with (output/"learning_rate_comparison.csv").open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        return rows


    @staticmethod
    def forest_search(args):
        protocol=ScheduledSearch.setup_from_args(args)
        metadata=json.loads((args.cache/"metadata.json").read_text())
        train_base,val_base=(ScheduledSearch.load_split(args.cache,n,metadata) for n in ("train","validation"))
        validate_partition_disjointness({"train": train_base, "validation": val_base}, metadata)
        selection=[]
        for k in (3,5):
            ti=native_indices(train_base,k)
            td=crop_split(train_base,k,ti)
            effective, balance_audit = ScheduledSearch.fit_native_balance(td, metadata, protocol, args.output)
            mean,std=fit_normalization(td, metadata=metadata)
            env=(td.environment-mean[None,:,None,None])/std[None,:,None,None]
            ci=common_indices(val_base)
            vd=crop_split(val_base,k,ci)
            ve=(vd.environment-mean[None,:,None,None])/std[None,:,None,None]
            best=None
            for depth in (8,15,None):
                name=f"rf{k}_depth{depth}"
                path=args.output/"forests"/f"{name}.joblib"
                path.parent.mkdir(parents=True,exist_ok=True)
                summary_path=path.with_suffix(".json")
                if summary_path.exists():
                    summary=json.loads(summary_path.read_text())
                    if summary.get("categorical_balance") != balance_audit:
                        raise ValueError("Saved forest summary categorical balancing differs from the native training cohort")
                else:
                    if path.exists():
                        # A completed forest save interrupted before its summary
                        # can be safely recovered without fitting or overwriting it.
                        model=PatchRandomForest.load(path)
                        if model.metadata.get("categorical_balance") != balance_audit:
                            raise ValueError("Saved forest categorical balancing differs from the native training cohort")
                    else:
                        model=PatchRandomForest(k,n_estimators=args.forest_trees,max_depth=depth,random_state=args.seed,n_jobs=args.threads)
                    start=time.perf_counter()
                    if not path.exists():model.fit(env,td.burned,td.target,effective,channel_names=metadata["channels"])
                    p=model.predict_probability(ve,vd.burned,channel_names=metadata["channels"])
                    score=brier(vd.target,p,vd.weight)
                    if not path.exists():model.save(path,metadata=dict(normalization_mean=mean.tolist(),normalization_std=std.tolist(),cache_metadata_sha256=protocol["cache_sha256"]["metadata.json"],categorical_balance=balance_audit,
                                                                        categorical_balance_settings=protocol["categorical_balance_settings"]))
                    reload=PatchRandomForest.load(path)
                    np.testing.assert_allclose(p,reload.predict_probability(ve,vd.burned,channel_names=metadata["channels"]),rtol=0,atol=1e-12)
                    summary=dict(id=name,family="random_forest",kernel_size=k,max_depth=depth,n_estimators=args.forest_trees,
                                 checkpoint=str(path.resolve()),validation_common_brier=score,train_sample_count=len(td),
                                 checkpoint_sha256=ScheduledSearch.sha256(path),
                                 fit_seconds=time.perf_counter()-start,test_used_for_selection=False,categorical_balance=balance_audit)
                    write_json(summary_path,summary)
                    print(f"{name} val_common={score:.7f} seconds={summary['fit_seconds']:.1f}",flush=True)
                selection.append(summary)
                if best is None or summary["validation_common_brier"]<best["validation_common_brier"]:best=summary
            del env,ve,td,vd
        write_json(args.output/"forest_selection.json",selection)
        write_json(args.output/"forests_complete.json",dict(completed=True,candidates=len(selection),test_used_for_selection=False))


    @staticmethod
    def thresholds(data,p,indices):
        return {name:select_classification_threshold(data.target[indices],p[indices],data.weight[indices],criterion=name) for name in ("f1","mcc")}


    @staticmethod
    def finalize(args):
        if not all((args.output/name).exists() for name in ("neural_complete.json","forests_complete.json")):
            raise ValueError("Neural and forest searches must finish before test evaluation")
        protocol=ScheduledSearch.setup_from_args(args)
        ScheduledSearch.verify_protocol(protocol,args.cache)
        metadata=json.loads((args.cache/"metadata.json").read_text())
        summaries=json.loads((args.output/"candidate_selection.json").read_text())
        forests=json.loads((args.output/"forest_selection.json").read_text())
        ScheduledSearch.verify_balance_reports(args.output, protocol, summaries + forests)
        selected=[]
        for family in ("constant","linear",*ScheduledSearch.NEURAL_FAMILIES):
            for k in ScheduledSearch.SIZES:
                selected.append(min((s for s in summaries if s["candidate"]["family"]==family and s["candidate"]["kernel_size"]==k),key=lambda s:s["validation_common_brier"]))
        for k in (3,5):selected.append(min((s for s in forests if s["kernel_size"]==k),key=lambda s:s["validation_common_brier"]))
        best=min(selected,key=lambda s:s["validation_common_brier"])
        for record in selected:
            if record.get("checkpoint_sha256") != ScheduledSearch.sha256(record["checkpoint"]):
                raise ValueError(f"Selected checkpoint integrity mismatch: {record['checkpoint']}")
            ScheduledSearch.verify_checkpoint_balance(record)
        write_json(args.output/"selection.json",dict(selected=selected,best=best,test_used_for_selection=False))
        write_json(args.output/"best_models.json",{name:record for record in selected for name in [
            f"{record['candidate']['family']}_k{record['candidate']['kernel_size']}" if "candidate" in record
            else f"random_forest_k{record['kernel_size']}"]})
        # This is the first stage loading test inputs/outcomes.
        metrics={};calibration_thresholds={};identities={}
        for split in ("validation","test","train"):
            data=ScheduledSearch.load_split(args.cache,split,metadata)
            identities[split] = cell_hour_identities(data)
            common=common_indices(data)
            payload=cohort_payload(data,common)
            native_cohorts={k:native_indices(data,k) for k in ScheduledSearch.SIZES}
            rows={}
            for record in selected:
                if "candidate" in record:
                    c=record["candidate"];name=c["id"];k=c["kernel_size"]
                    fitted=ScheduledSearch.load_trained_model(record["checkpoint"],args.device)
                    cropped=crop_split(data,k)
                    mean=fitted.mean[:,0,0].cpu().numpy();std=fitted.std[:,0,0].cpu().numpy()
                    tensors=ScheduledSearch.tensor_data(cropped,mean,std,c["family"],choose_device(args.device))
                    p=ScheduledSearch.probabilities(fitted.model,tensors)
                    no_contact=cropped.neighbor_count==0
                    if not np.all(p[no_contact]==0):raise AssertionError("Kernel no-contact probabilities must be structural zeros")
                    coverage=dict(predicted_count=len(p),no_contact_count=int(no_contact.sum()),no_contact_probability_max=float(p[no_contact].max()) if no_contact.any() else None)
                    del tensors,fitted
                else:
                    name=record["id"];k=record["kernel_size"]
                    fitted=PatchRandomForest.load(resolve_recorded_path(record["checkpoint"]))
                    preprocessing=fitted.metadata
                    mean=np.array(preprocessing["normalization_mean"],dtype=np.float32);std=np.array(preprocessing["normalization_std"],dtype=np.float32)
                    cropped=crop_split(data,k)
                    p=np.empty(len(data),dtype=np.float64)
                    for start in range(0,len(data),8192):
                        end=min(start+8192,len(data));e=(cropped.environment[start:end]-mean[None,:,None,None])/std[None,:,None,None]
                        p[start:end]=fitted.predict_probability(e,cropped.burned[start:end],channel_names=metadata["channels"])
                    coverage=dict(predicted_count=len(p),no_contact_count=int((cropped.neighbor_count==0).sum()),no_contact_probability_max=float(p[cropped.neighbor_count==0].max()) if (cropped.neighbor_count==0).any() else None)
                ni=native_cohorts[k]
                if split=="validation":
                    reproduced=brier(data.target[common],p[common],data.weight[common])
                    if not math.isclose(reproduced,record["validation_common_brier"],rel_tol=0,abs_tol=2e-6):
                        raise AssertionError(f"Selected checkpoint validation score mismatch: {name}")
                    calibration_thresholds[name]={"common":ScheduledSearch.thresholds(data,p,common),"native":ScheduledSearch.thresholds(data,p,ni)}
                t=calibration_thresholds[name]
                rows[name]=dict(kernel_size=k,coverage=coverage,
                                native=probability_metrics_with_all(data.target[ni],p[ni],data.weight[ni],cropped.neighbor_count[ni],thresholds=t["native"]),
                                common=probability_metrics_with_all(data.target[common],p[common],data.weight[common],cropped.neighbor_count[common],thresholds=t["common"]))
                rows[name]["categorical_groups"] = {
                    "native": categorical_group_metrics(cropped, p, metadata, indices=ni),
                    "common": categorical_group_metrics(cropped, p, metadata, indices=common),
                }
                rows[name]["native"]["calibration"]=weighted_calibration(data.target[ni],p[ni],data.weight[ni])
                rows[name]["common"]["calibration"]=weighted_calibration(data.target[common],p[common],data.weight[common])
                payload[name]=p[common]
                dest=args.output/"predictions"/split;dest.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(dest/f"{name}.npz",p=p,source_index=np.arange(len(data)),native_index=ni,common_index=common)
            dest=args.output/"predictions";dest.mkdir(exist_ok=True)
            np.savez_compressed(dest/f"{split}_common.npz",**payload)
            metrics[split]=dict(common_cohort=cohort_summary(data,common,3),native_cohorts={str(k):cohort_summary(data,native_cohorts[k],k) for k in ScheduledSearch.SIZES},models=rows)
            write_json(args.output/"metrics.json",metrics)
            del data
        write_json(args.output/"classification_thresholds.json",calibration_thresholds)
        partition_verification = validate_partition_disjointness(identities, metadata)
        write_json(args.output/"partition_verification.json", partition_verification)
        ScheduledSearch.report(args.output,protocol,selected,best,metrics)
        ScheduledSearch.verify_protocol(protocol,args.cache)
        write_json(args.output/"complete.json",dict(completed=True,neural_candidates=len(summaries),forest_candidates=len(forests),evaluated_models=len(selected),
                                                  test_used_for_selection=False,cache_sha256_verified={n:ScheduledSearch.sha256(args.cache/n)==v for n,v in protocol["cache_sha256"].items()}))


    @staticmethod
    def report(output,protocol,selected,best,metrics):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        def label(s):
            c=s.get("candidate",s)
            return f"{c.get('family')} {c['kernel_size']}x{c['kernel_size']}"
        def name(s):return s.get("candidate",s)["id"]
        def fmt(v):return f"{v:.6f}" if isinstance(v,(float,int)) else str(v)
        partition_description = ScheduledSearch.split_description(protocol)
        rate_text = ", ".join(f"{value:g}" for value in protocol["learning_rates"])
        schedule_text = ", ".join(protocol["schedules"])
        lines=["# Fresh kernel learning-rate and scheduling search", "",f"Validation selected **{label(best)}** among the searched configurations. All test scores below were computed after selection.","",
               partition_description,"",ScheduledSearch.balance_description(protocol),"",
               "The target is a currently unburned cell becoming burned at exactly the next hourly snapshot. Contact uses the reconstructed current cumulative burned-area map; it does not mean an actively flaming cell.","",
               f"Every candidate completed {protocol['candidate_epochs']} full-batch epochs. One validation-selected candidate in each of four neural families continued, with optimizer and RNG state, to {protocol['finalist_epochs']} epochs. There was no early stopping. A saved prediction checkpoint can occur before the final epoch because selection minimizes validation Brier over the entire trajectory.","",
               "All fits are fresh. Constant kernels learn offset-specific rates; linear kernels map per-channel environmental patch means to nonnegative rates; MLP and residual MLP families use the same patch means; the existing CNN and new regularized CNN preserve full spatial environmental patches. Every kernel fixes its center to zero and computes q=1-exp(-sum(nonnegative offset rate × current burned neighbor)). Random forests are separate probability-classifier baselines, not learned rate kernels.","",
               "Training uses native K-contact rows from one frozen 9x9 sample cache and its original inverse inclusion weights. Native evaluation also uses K-contact. The matched comparison uses the exact same current 3x3-contact rows for every model, retaining the original weights. No-contact predictions are saved for every model; neural kernels return a valid structural zero, and forests may return nonzero probabilities.","",
               f"Optimization is AdamW with full-batch categorical optimization-weighted Brier divided by optimization-weighted training prevalence, weight decay, optional dropout, and gradient norm clipping at 10. An epoch is one pass over every native training row and ONE optimizer step, with chunked gradient accumulation. The ten joint architecture/regularization settings and four kernel sizes are each crossed with peak learning rates **{rate_text}** and schedules **{schedule_text}**, giving {len(protocol['candidates'])} kernel candidates. Width, depth, dropout, and weight decay retain the prior joint search settings. The learning-rate/schedule subgrid is fully crossed; the architecture search remains finite and joint.","",
               f"The fixed scheduling horizon is **{protocol['scheduling_horizon']} optimizer steps from the start of every candidate**, even when its initial fit stops after {protocol['candidate_epochs']} steps. Continuing a finalist restores its AdamW and RNG states and resumes the original schedule. It does not start warmup again or rebase the cosine schedule. Warmup lasts {protocol['warmup_epochs']} steps; the rate floor is {protocol['minimum_lr_factor']:g} times the peak; optional restart cycles last {protocol['restart_period']} steps. The rate actually used is saved at every epoch as `learning_rate`, with a one-based `optimizer_step`.","",
               "Constant schedules always use the peak. Linear warmup uses peak × step / warmup_length. For a nonzero warmup, ordinary cosine uses floor + (peak − floor) × (1 + cos(π × (step − warmup_length)/(horizon − warmup_length)))/2 after warmup and reaches the floor at the fixed horizon. Without warmup its cosine progress is (step − 1)/(horizon − 1). Restart schedules use cycles with progress 0/(period − 1), …, (period − 1)/(period − 1) after warmup, then restart at the peak. Scheduling never consults validation or test scores.","",
               "Every variant of the same kernel/architecture/regularization setting shares its initial parameter checksum and random seed. AdamW's nominal weight-decay coefficient stays fixed within each comparison, but its per-step shrinkage multiplier is 1 − learning_rate × weight_decay, so changing rates or schedules also changes integrated parameter shrinkage. The controlled comparison below therefore measures the complete optimizer policy at fixed nominal regularization. It does not isolate learning rate from accumulated weight decay.","",
               "## Matched test comparison", "", "| Model | Completed / selected epoch | Validation Brier | Test Brier | AP | ROC AUC | Exact NLL | F1 at validation threshold | MCC at validation threshold |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        csv_rows=[]
        for s in sorted(selected,key=lambda s:s["validation_common_brier"]):
            n=name(s);m=metrics["test"]["models"][n]["common"]
            epoch=f"{s['epochs_completed']} / {s['best_epoch']}" if "epochs_completed" in s else "trees"
            policy = f"; peak={s['candidate']['learning_rate']:g}, {s['candidate']['scheduler']['name']}" if "candidate" in s else ""
            lines.append(f"| {label(s)}{policy} | {epoch} | {fmt(s['validation_common_brier'])} | {fmt(m['brier'])} | {fmt(m['average_precision'])} | {fmt(m['roc_auc'])} | {fmt(m['exact_negative_log_likelihood_mean'])} | {fmt(m['f1_at_validation_f1_threshold'])} | {fmt(m['mcc_at_validation_mcc_threshold'])} |")
            csv_rows.append(dict(model=n,label=label(s),validation_brier=s["validation_common_brier"],**{key:value for key,value in m.items() if not isinstance(value,(list,dict))}))
        lines += ["", "## Cohort sizes", "", "| Split | Full prediction rows | 3x3 contact | 5x5 contact | 7x7 contact | 9x9 contact | Matched positives |", "|---|---:|---:|---:|---:|---:|---:|"]
        for split in ("train","validation","test"):
            c=metrics[split];lines.append(f"| {split} | {c['common_cohort']['base_sample_count']} | " + " | ".join(str(c["native_cohorts"][str(k)]["sample_count"]) for k in ScheduledSearch.SIZES)+f" | {c['common_cohort']['positive_sample_count']} |")
        lines += ["", "## Native test comparison", "", "These scores use different K-contact populations and therefore cannot rank kernel sizes fairly. Compare model families within the same K, or use the matched table above.","", "| Model | Native test Brier | Native AP | Native ROC AUC |", "|---|---:|---:|---:|"]
        for s in selected:
            m=metrics["test"]["models"][name(s)]["native"]
            lines.append(f"| {label(s)} | {fmt(m['brier'])} | {fmt(m['average_precision'])} | {fmt(m['roc_auc'])} |")
        comparisons=json.loads((output/"learning_rate_comparison.json").read_text())["rows"]
        lines += ["", "## Controlled learning-rate and schedule comparison", "",
                  f"Each row below fixes kernel size, architecture, dropout, weight decay, training rows, normalization, initialization, and seed. Every entry is its minimum matched validation Brier through the same first {protocol['candidate_epochs']} steps. Later finalist outcomes are excluded from this table. Full candidate trajectories and end-of-budget values are in `learning_rate_comparison.csv` and `history.json`.","",
                  "| Fixed base configuration | " + " | ".join(f"{rate:g} {schedule}" for rate in protocol["learning_rates"] for schedule in protocol["schedules"]) + " |",
                  "|---|" + "---:|"*(len(protocol["learning_rates"])*len(protocol["schedules"]))]
        for base in dict.fromkeys(row["base_configuration_id"] for row in comparisons):
            variant={(row["peak_learning_rate"],row["schedule"]):row for row in comparisons if row["base_configuration_id"]==base}
            lines.append(f"| {base} | " + " | ".join(fmt(variant[(rate,schedule)]["validation_common_brier"]) for rate in protocol["learning_rates"] for schedule in protocol["schedules"]) + " |")
        summaries=json.loads((output/"candidate_selection.json").read_text())
        by_id={name(row):row for row in summaries}
        finalists=json.loads((output/"finalist_selection.json").read_text())["selection_before_extension"]
        finalists=[by_id[name(row)] for row in finalists]
        fig,axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
        lr_fig,lr_axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
        diagnostics={}
        for ax,lr_ax,family in zip(axes.flat,lr_axes.flat,ScheduledSearch.NEURAL_FAMILIES):
            s=next(row for row in finalists if row["candidate"]["family"]==family)
            h=json.loads((output/"candidates"/name(s)/"history.json").read_text())
            x=np.array([r["epoch"] for r in h]);v=np.array([r["validation_common_brier"] for r in h]);tr=np.array([r["train_common_brier"] for r in h])
            ax.plot(x,tr,label="matched training Brier");ax.plot(x,v,label="matched validation Brier")
            ax.axvline(protocol["candidate_epochs"],color="gray",linestyle=":",label="end of initial search")
            ax.scatter([s["best_epoch"]],[s["validation_common_brier"]],color="red",s=25,zorder=4,label="selected checkpoint")
            ax.set(xscale="log",xlabel="Epoch (log scale)",ylabel="Weighted Brier",title=f"{label(s)}; full {len(h)} epochs")
            ax.legend(fontsize=8)
            actual_lr=np.array([r["learning_rate"] for r in h])
            lr_ax.plot(x,actual_lr,label="actual optimizer learning rate")
            lr_ax.axvline(protocol["candidate_epochs"],color="gray",linestyle=":",label="end of initial search")
            lr_ax.set(xlabel="Optimizer step (= epoch)",ylabel="Learning rate",title=f"{label(s)}; {s['candidate']['scheduler']['name']}; peak={s['candidate']['learning_rate']:g}")
            lr_ax.legend(fontsize=8)
            early=min(v[:protocol["candidate_epochs"]]);late=min(v[protocol["candidate_epochs"]:]) if len(v)>protocol["candidate_epochs"] else None
            diagnostics[family]=dict(candidate=name(s),best_first_stage_validation_brier=float(early),best_late_validation_brier=float(late) if late is not None else None,
                                     relative_late_improvement=(float((early-late)/early) if late is not None else None),
                                     best_epoch=s["best_epoch"],final_training_brier=float(tr[-1]),minimum_training_brier=float(tr.min()),
                                     peak_learning_rate=s["candidate"]["learning_rate"],scheduler=s["candidate"]["scheduler"],
                                     initial_learning_rate=float(actual_lr[0]),final_learning_rate=float(actual_lr[-1]),
                                     interpretation="Descriptive late improvement only. " + partition_description + " No verified interpolation threshold or multi-seed grokking claim.")
        fig.savefig(output/"learning_curves.png",dpi=180);plt.close(fig)
        lr_fig.savefig(output/"learning_rate_curves.png",dpi=180);plt.close(lr_fig)
        write_json(output/"learning_diagnostics.json",diagnostics)
        lines += ["", "## Long-training observations", "", "![Learning curves](learning_curves.png)","",
                  "These panels show the four candidates selected for uninterrupted long training. A family/kernel winner in the test table can be a different, shorter candidate when it has a better validation checkpoint.","",
                  "![Actual optimizer learning rates](learning_rate_curves.png)","",
                  "The learning-rate panels plot rates read back from the saved per-step histories. Constant-rate controls remain available for interpreting delayed generalization without a changing learning rate. An improvement during rate decay, or after a restart, is associated with the chosen optimizer policy and alone does not establish grokking.","",
                  f"These curves show training and validation Brier under the same current 3x3-contact condition. {partition_description} Native training Brier is also saved in each history. A decrease after epoch {protocol['candidate_epochs']} is descriptive evidence of late validation improvement. Grokking requires a demonstrated memorization phase followed by delayed generalization; double descent requires a reproducible rise and subsequent fall around an interpolation regime. Neither is inferred automatically from a long run or a visually noisy curve. The references concern particular experimental settings and do not guarantee either phenomenon on reconstructed wildfire labels.","",
                  "[Grokking paper](https://arxiv.org/abs/2201.02177) and [Deep Double Descent paper](https://arxiv.org/abs/1912.02292).", ""]
        for family,d in diagnostics.items():
            lines.append(f"- {family}: best validation Brier through epoch {protocol['candidate_epochs']}={d['best_first_stage_validation_brier']:.6f}; after epoch {protocol['candidate_epochs']}={fmt(d['best_late_validation_brier'])}; selected epoch={d['best_epoch']}; minimum matched training Brier={d['minimum_training_brier']:.6f}.")
        lines += ["", "## Saved artifacts and limits", "", "`protocol.json` binds all input cache hashes, source hashes and the prespecified search. `candidate_selection.json`, `finalist_selection.json` and `selection.json` record validation-only selection. Candidate folders contain the complete per-epoch histories, selected public checkpoints and resumable final optimizer/RNG states. `predictions/` retains probabilities for all base rows and matched identities/weights. `metrics.json` retains calibration, exact and clipped NLL, Bernoulli distances, KL, AP, PR AUC, F1 and MCC. Classification thresholds are selected independently on native and matched validation populations.","",
                  "The training labels are retrospective reconstructions. Scores are inverse-inclusion-weighted sampled estimates, not exact full-grid population scores. No active-flame residence assumption was introduced. The search uses one seed and does not establish robustness, a globally best parameter setting, double descent, or grokking.", ""]
        if protocol.get("smoke_verification_only"):
            lines[2:2] = ["**EXECUTION VERIFICATION ONLY.** This short run uses a small sampled subset of the real cache and reduced epoch/tree budgets. Its numerical scores verify the pipeline and must not be used as scientific model rankings, population estimates, or evidence of grokking/double descent.", ""]
        (output/"report.md").write_text("\n".join(lines))
        fields=sorted(set().union(*(r.keys() for r in csv_rows)))
        with (output/"metrics.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(csv_rows)


    @staticmethod
    def run_all(args):
        ScheduledSearch.train_search(args)
        ScheduledSearch.forest_search(args)
        ScheduledSearch.finalize(args)


    @staticmethod
    def smoke(args):
        """Run every family/stage on real cache subsets with a short epoch budget."""
        source=args.cache
        if args.output==ScheduledSearch.DEFAULT_OUTPUT:args.output=ScheduledSearch.DEFAULT_SMOKE_OUTPUT
        destination=args.output/"smoke_cache"
        if not destination.exists():
            metadata=json.loads((source/"metadata.json").read_text())
            destination.mkdir(parents=True)
            rng=np.random.default_rng(args.seed)
            sampling={}
            for split in ("train","validation","test"):
                data=ScheduledSearch.load_split(source,split,metadata)
                count=512 if split=="train" else 256
                c3=data.burned[:,:,3:6,3:6].sum((1,2,3))>0
                c9=data.neighbor_count>0
                groups=[c3 & (data.target==label) for label in (0,1)] + [~c9 & (data.target==label) for label in (0,1)]
                indices=[]
                for mask in groups:
                    candidates=np.flatnonzero(mask)
                    indices.extend(rng.choice(candidates,min(32,len(candidates)),replace=False).tolist())
                remaining=np.setdiff1d(np.arange(len(data)),indices)
                indices=np.sort(np.r_[indices,rng.choice(remaining,count-len(indices),replace=False)]).astype(np.int64)
                payload={key:getattr(data,key)[indices] for key in CachedSplit.__dataclass_fields__}
                np.savez_compressed(destination/f"{split}.npz",**payload,original_base_index=indices)
                sampling[split]=dict(base_rows=len(data),smoke_rows=count,seed=args.seed)
            metadata.update(smoke_verification_only=True,smoke_original_cache=str(source.resolve()),smoke_sampling=sampling)
            write_json(destination/"metadata.json",metadata)
        args.cache=destination;args.epochs=2;args.finalist_epochs=4;args.forest_trees=9
        args.warmup_epochs=1;args.restart_period=2
        ScheduledSearch.run_all(args)


    @staticmethod
    def parser():
        p=argparse.ArgumentParser(description=ScheduledSearch.__doc__)
        p.add_argument("stage",choices=("run","smoke","train","forests","finalize"))
        p.add_argument("--cache",type=Path,default=ScheduledSearch.DEFAULT_CACHE)
        p.add_argument("--output",type=Path,default=ScheduledSearch.DEFAULT_OUTPUT)
        p.add_argument("--epochs",type=int,default=512)
        p.add_argument("--finalist-epochs",type=int,default=4096)
        p.add_argument("--learning-rates",type=float,nargs="+",default=list(ScheduledSearch.DEFAULT_LEARNING_RATES),
                       help="Peak rates crossed with every fixed kernel/architecture/regularization configuration")
        p.add_argument("--schedules",choices=SCHEDULES,nargs="+",default=list(ScheduledSearch.DEFAULT_SCHEDULES),
                       help="constant controls and warmup_cosine by default; optionally add warmup_cosine_restarts")
        p.add_argument("--warmup-epochs",type=int,default=32,help="Linear warmup steps for nonconstant schedules")
        p.add_argument("--minimum-lr-factor",type=float,default=.01,help="Cosine floor as a fraction of the peak learning rate")
        p.add_argument("--restart-period",type=int,default=512,help="Post-warmup optimizer steps per optional cosine restart cycle")
        p.add_argument("--seed",type=int,default=7)
        add_categorical_balance_arguments(p)
        p.add_argument("--threads",type=int,default=4)
        p.add_argument("--forest-trees",type=int,default=100)
        p.add_argument("--device",default="auto",help="auto chooses MPS, then CUDA, then CPU; resume requires same training device")
        return p


    @staticmethod
    def main():
        args=ScheduledSearch.parser().parse_args()
        if args.device=="auto":args.device="mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        if args.epochs<1 or args.finalist_epochs<args.epochs or args.threads<1:
            raise ValueError("Epochs/threads must be positive and finalist budget must include initial training")
        {"run":ScheduledSearch.run_all,"smoke":ScheduledSearch.smoke,"train":ScheduledSearch.train_search,"forests":ScheduledSearch.forest_search,"finalize":ScheduledSearch.finalize}[args.stage](args)


class MixedSearch:
    """Fresh single-scale and mixed-kernel searches with fixed learning-rate schedules.

    The declared partitions, labels and inverse sampling weights come from one
    frozen 9x9 cache. Each model trains on its K-contact rows. Hyperparameters,
    epochs, finalists and classification thresholds use validation only. Final
    test predictions cover every base-cache row; comparison metrics use native
    K-contact and identical 3-contact cohorts. No early stopping is used.
    """

    __doc__ = __doc__.replace("\n    ", "\n")
    __file__ = __file__
    split_contract_fields = staticmethod(Search.split_contract_fields)
    split_description = staticmethod(Search.split_description)
    fit_native_balance = staticmethod(Search.fit_native_balance)
    bind_tensor_balance = staticmethod(Search.bind_tensor_balance)
    balance_description = staticmethod(Search.balance_description)
    validate_categorical_normalization = staticmethod(Search.validate_categorical_normalization)
    verify_balance_reports = staticmethod(Search.verify_balance_reports)
    verify_checkpoint_balance = staticmethod(Search.verify_checkpoint_balance)
    PatchRandomForest = staticmethod(PatchRandomForest)
    brier = staticmethod(brier)
    probability_metrics_with_all = staticmethod(probability_metrics_with_all)
    balance_settings_from_args = staticmethod(balance_settings_from_args)
    initialize_mixed_kernel_rate = staticmethod(initialize_mixed_kernel_rate)
    load_split = staticmethod(load_split)
    TRAINING_SOURCE_FILES = CANONICAL_TRAINING_SOURCE_FILES

    RUNS = PATH_RUNS
    DEFAULT_CACHE = RUNS / "20261009_weighted_stratified_split/prepared_all"
    DEFAULT_OUTPUT = RUNS / "20261009_mixed_kernel_search_weighted_stratified_categorical_balanced"
    DEFAULT_SMOKE_OUTPUT = RUNS / "20261009_mixed_kernel_smoke_weighted_stratified_categorical_balanced"
    DEFAULT_LEARNING_RATES = (.001, .003, .01, .03)
    DEFAULT_SCHEDULES = ("constant", "warmup_cosine")
    SIZES = (3, 5, 7, 9)
    NEURAL_FAMILIES = ("legacy", "cnn", "mlp", "residual_mlp", "mixed")
    SPATIAL_FAMILIES = ("legacy", "cnn", "mixed")
    MIXED_SIZES = (3, 5, 7, 9)


    @staticmethod
    def sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


    @staticmethod
    def candidate_plan(learning_rates=DEFAULT_LEARNING_RATES, schedules=DEFAULT_SCHEDULES,
                       horizon=4096, warmup_epochs=32, minimum_lr_factor=.01, restart_period=512):
        """Cross single-scale and mixed architecture settings with rates and schedules.

        For each kernel/architecture setting, every variant receives the same seed,
        initialization, training cohort, normalization, dropout, and weight decay.
        This is a full rate-by-schedule crossing over a joint architecture search.
        """
        learning_rates = tuple(float(value) for value in learning_rates)
        schedules = tuple(schedules)
        if not learning_rates or len(set(learning_rates)) != len(learning_rates):
            raise ValueError("Learning rates must be a nonempty list without duplicates")
        if any(not math.isfinite(rate) or rate <= 0 for rate in learning_rates):
            raise ValueError("Learning rates must be finite and positive")
        if not schedules or len(set(schedules)) != len(schedules):
            raise ValueError("Schedules must be a nonempty list without duplicates")
        scheduler_configurations = [validate_scheduler(dict(name=name, horizon=horizon, warmup_epochs=warmup_epochs,
                                                           minimum_lr_factor=minimum_lr_factor, restart_period=restart_period))
                                    for name in schedules]
        configurations = [
            ("constant", 1, 1, 0., .01, 0.),
            ("linear", 1, 1, 0., .01, .0001),
            ("legacy", 16, 1, 0., .001, .0001),
            ("cnn", 32, 1, .15, .003, .001),
            ("mlp", 8, 2, 0., .003, 0.),
            ("mlp", 32, 2, .15, .003, .0001),
            ("mlp", 128, 2, .15, .003, .01),
            ("mlp", 32, 4, 0., .001, .1),
            ("residual_mlp", 32, 3, .15, .003, .001),
            ("residual_mlp", 128, 3, .15, .001, .01),
        ]
        plan = []
        for k in MixedSearch.SIZES:
            for index, (family, width, depth, dropout, _, decay) in enumerate(configurations):
                base_id = f"k{k}_{family}_{index:02d}"
                for rate in learning_rates:
                    for scheduler in scheduler_configurations:
                        plan.append(dict(id=f"{base_id}_lr{rate!r}_{scheduler['name']}",
                                         base_configuration_id=base_id, kernel_size=k, family=family,
                                         hidden_channels=width, depth=depth, dropout=dropout,
                                         learning_rate=rate, weight_decay=decay, scheduler=dict(scheduler)))
        # Independent environmental CNNs at every scale; global nonnegative mixing.
        # The support is the union (maxK=9), not a separately scored single scale.
        for index, (width, dropout, decay) in enumerate(((16, 0., .0001), (32, .15, .001), (64, .15, .01))):
            base_id = f"mixed_3_5_7_9_{index:02d}"
            for rate in learning_rates:
                for scheduler in scheduler_configurations:
                    plan.append(dict(id=f"{base_id}_lr{rate!r}_{scheduler['name']}",
                                     base_configuration_id=base_id, kernel_size=max(MixedSearch.MIXED_SIZES), family="mixed",
                                     kernel_sizes=list(MixedSearch.MIXED_SIZES), branch_architecture="cnn",
                                     mixing_constraint="nonnegative", hidden_channels=width, depth=1, dropout=dropout,
                                     learning_rate=rate, weight_decay=decay, scheduler=dict(scheduler)))
        return plan


    @staticmethod
    def load_trained_model(path, device="cpu"):
        """Dispatch saved inference without modifying the previous frozen loader."""
        architecture = torch.load(resolve_recorded_path(path), map_location="cpu", weights_only=True)["contract"]["architecture"]
        return (load_mixed_trained_model if architecture == "MixedNonnegativeKernel" else load_single_trained_model)(path, device)


    @staticmethod
    def verify_protocol(protocol, cache):
        """Reject input/code drift before resuming or exposing test outcomes."""
        if str(cache.resolve()) != protocol["cache"]:
            raise ValueError("Cache path differs from the frozen experiment protocol")
        for name, expected in protocol["cache_sha256"].items():
            if MixedSearch.sha256(cache / name) != expected:
                raise ValueError(f"Cache integrity mismatch: {name}; use a new output directory for changed inputs")
        for name, expected in protocol["training_source_sha256"].items():
            if not (Path(__file__).parent / name).is_file() or MixedSearch.sha256(Path(__file__).parent / name) != expected:
                raise ValueError(f"Training source integrity mismatch: {name}; use a new output directory for changed code")


    @staticmethod
    def setup(output, cache, epochs, finalist_epochs, seed, forest_trees=100, *,
              learning_rates=DEFAULT_LEARNING_RATES, schedules=DEFAULT_SCHEDULES,
              warmup_epochs=32, minimum_lr_factor=.01, restart_period=512, balance_settings=None):
        balance_settings = validate_categorical_balance_settings(**(balance_settings or {}))
        if epochs < 1 or finalist_epochs < epochs:
            raise ValueError("Candidate epochs must be positive and fit inside the finalist horizon")
        candidates = MixedSearch.candidate_plan(learning_rates, schedules, finalist_epochs, warmup_epochs,
                                    minimum_lr_factor, restart_period)
        settings = dict(learning_rates=[float(v) for v in learning_rates], schedules=list(schedules),
                        scheduling_horizon=finalist_epochs, warmup_epochs=warmup_epochs,
                        minimum_lr_factor=float(minimum_lr_factor), restart_period=restart_period,
                        categorical_balance_settings=balance_settings)
        output.mkdir(parents=True, exist_ok=True)
        path = output / "protocol.json"
        if path.exists():
            protocol = json.loads(path.read_text())
            for key, value in {"cache": str(cache.resolve()), "candidate_epochs": epochs,
                               "finalist_epochs": finalist_epochs, "seed": seed, "forest_trees": forest_trees,
                               **settings, "candidates": candidates}.items():
                if protocol[key] != value:
                    raise ValueError(f"Resume protocol mismatch: {key}")
            MixedSearch.verify_protocol(protocol, cache)
            return protocol
        metadata = json.loads((cache / "metadata.json").read_text())
        validate_split_metadata(metadata, require_all_partitions=True)
        if metadata["dt_hours"] != 1. or metadata["kernel_size"] != 9:
            raise ValueError("The experiment requires the frozen one-hour 9x9 base cache")
        hashes = {name: MixedSearch.sha256(cache / name) for name in ("metadata.json", "train.npz", "validation.npz", "test.npz")}
        source_checks = []
        root = resolve_source_root(metadata)
        for source in metadata.get("source_files", []):
            actual = root / source["path"]
            if not actual.is_file() or MixedSearch.sha256(actual) != source["sha256"]:
                raise ValueError(f"Source integrity mismatch: {actual}")
            source_checks.append(source["path"])
        sources = {name: MixedSearch.sha256(Path(__file__).parent / name) for name in MixedSearch.TRAINING_SOURCE_FILES}
        protocol = dict(cache=str(cache.resolve()), candidate_epochs=epochs, finalist_epochs=finalist_epochs,
                        seed=seed, forest_trees=forest_trees, kernel_sizes=list(MixedSearch.SIZES), candidates=candidates, **settings,
                        training="Native K-contact cells from one frozen base sampling design; complete known context; current center unburned",
                        contact="At least one off-center cell already burned at time t inside centered KxK; cumulative reconstructed burned map, not active flame",
                        common="Identical original 9x9 cache rows with contact inside centered 3x3; original labels and inverse inclusion weights",
                        selection="Minimum float64 inverse-weighted common-contact validation Brier; checkpoint and hyperparameters before test",
                        long_finalists="One globally validation-selected candidate per neural family (legacy, cnn, mlp, residual_mlp, mixed), continued from last optimizer state to the full finalist epoch budget",
                        optimizer="AdamW, full-batch categorical optimization-weighted Brier/optimization prevalence, explicit prespecified rate before every optimizer step, decay on all parameters, no early stopping",
                        schedule="One-based optimizer steps; the full finalist horizon is fixed from step one, including candidates initially trained only to the candidate budget; no validation-triggered scheduling",
                        controlled_comparison="Peak rate and schedule crossed within each fixed kernel/architecture/regularization configuration, sharing initialization and seed; compare first-stage validation trajectories at identical epoch budgets",
                        weight_decay_interpretation="AdamW decay multiplies each parameter by (1-learning_rate*weight_decay) per optimizer step; equal nominal decay with different schedules does not imply equal integrated shrinkage",
                        prediction="All original base-cache rows, including no-contact inputs; neural kernel structural zero for known no-contact",
                        test_used_for_selection=False, cache_sha256=hashes, training_source_sha256=sources,
                        verified_source_files=len(source_checks), target="unburned at t becomes burned at exactly t+3600s",
                        limitations=["Retrospective reconstructed hourly labels; not independent observed active flames",
                                     "Best among the finite prespecified joint configurations; not a global optimum",
                                     "Five single-seed neural finalists; curves can suggest delayed generalization, not prove grokking or double descent"],
                        versions=dict(python=platform.python_version(), numpy=np.__version__, torch=str(torch.__version__)),
                        references=["https://arxiv.org/abs/2201.02177", "https://arxiv.org/abs/1912.02292"])
        protocol["mixed_model"] = dict(kernel_sizes=list(MixedSearch.MIXED_SIZES), branch_architecture="cnn",
            mixing_constraint="nonnegative", mixing="Global jointly learned softplus scalar weights with unrestricted sum",
            rate="sum_K alpha_K sum_offset kernel_K(offset) * current_burned(offset)",
            probability="1-exp(-combined_rate); one exponential after linear combination, not mixed branch probabilities",
            native_contact="9x9 union-support contact", common_contact="Identical centered 3x3 contact rows used by every model",
            identifiability="Mixing weights and branch amplitudes are not separately identifiable; weights are not causal scale importance")
        protocol.update(MixedSearch.split_contract_fields(metadata))
        protocol["training"] += "; split unit: " + protocol["split_unit"]
        protocol["smoke_verification_only"] = bool(metadata.get("smoke_verification_only", False))
        snapshot = output / "source_snapshot"
        snapshot.mkdir(exist_ok=True)
        for name in sources:
            (snapshot / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(__file__).parent / name, snapshot / name)
        write_json(path, protocol)
        return protocol


    @staticmethod
    def build(candidate, channels, device):
        if candidate["family"] == "mixed":
            model = build_mixed_kernel_model(channels, kernel_sizes=candidate["kernel_sizes"],
                branch_architecture=candidate["branch_architecture"], hidden_channels=candidate["hidden_channels"],
                depth=candidate["depth"], dropout=candidate["dropout"], mixing_constraint=candidate["mixing_constraint"])
        elif candidate["family"] == "legacy":
            model = EnvironmentConditionedConvolution(channels, candidate["kernel_size"], candidate["hidden_channels"])
        else:
            model = build_kernel_model(channels, candidate["kernel_size"], candidate["family"],
                                       candidate["hidden_channels"], candidate["depth"], candidate["dropout"])
        return model.to(device)


    @staticmethod
    def _pointwise(layer, value):
        """Exact affine/activation computation at one spatial output position."""
        if isinstance(layer, nn.Conv2d):
            return F.linear(value, layer.weight.flatten(1), layer.bias)
        if isinstance(layer, nn.Dropout2d):
            # At spatial shape 1x1, channel dropout equals scalar feature dropout.
            return F.dropout(value, layer.p, layer.training)
        if isinstance(layer, nn.Sequential):
            for member in layer:
                value = MixedSearch._pointwise(member, value)
            return value
        if hasattr(layer, "update"):
            return F.silu(value + MixedSearch._pointwise(layer.update, value))
        return layer(value)


    @staticmethod
    def cached_probability(model, features, burned):
        """Trusted validated feature path retaining the public model's parameters.

        Linear rather than 1x1 convolution avoids repeated GPU validation barriers.
        The full spatial first layer is a flattened dot product. CPU float64 and
        device float32 equivalence are checked before and after every fitted run.
        Dropout has the same law at the single output position.
        """
        if isinstance(model, MixedNonnegativeKernel):
            size = model.kernel_size
            environmental_patch = features.reshape(-1, model.in_channels, size, size)
            burned_patch = burned.reshape(-1, 1, size, size)
            rates = []
            for branch in model.branches.values():
                k = branch.kernel_size
                start = (size-k)//2
                environment = environmental_patch[:, :, start:start+k, start:start+k]
                source = burned_patch[:, :, start:start+k, start:start+k].flatten(1)
                branch_features = environment.flatten(1) if branch.architecture == "cnn" else environment.mean((2,3))
                network = branch.kernel_network
                if hasattr(network, "logits"):
                    logits = network.logits.reshape(1, -1).expand(len(features), -1)
                else:
                    hidden = F.linear(branch_features, network.spatial.weight.flatten(1), network.spatial.bias)
                    logits = MixedSearch._pointwise(network.output, MixedSearch._pointwise(network.hidden, hidden))
                rates.append((F.softplus(logits) * branch.off_center.flatten() * source).sum(dim=1))
            combined = (torch.stack(rates, dim=1) * model.mixing_weights()[None, :]).sum(dim=1)
            probability = -torch.expm1(-combined)
            return torch.where(burned_patch[:,0,size//2,size//2] == 1, 0, probability)
        network = model.kernel_network
        if isinstance(network, nn.Sequential):
            logits = MixedSearch._pointwise(network, features)
        elif hasattr(network, "logits"):
            logits = network.logits.reshape(1, -1).expand(len(features), -1)
        else:
            hidden = F.linear(features, network.spatial.weight.flatten(1), network.spatial.bias)
            logits = MixedSearch._pointwise(network.output, MixedSearch._pointwise(network.hidden, hidden))
        rate = (F.softplus(logits) * burned).sum(dim=1)
        return -torch.expm1(-rate)


    @dataclass
    class TensorData:
        features: torch.Tensor
        burned: torch.Tensor
        target: np.ndarray
        weight: np.ndarray
        target_tensor: torch.Tensor
        loss_weight: torch.Tensor
        common: np.ndarray
        optimization_weight: np.ndarray | None = None
        categorical_balance: dict | None = None


    @staticmethod
    def tensor_data(data, mean, std, family, device, common=None, *,
                    optimization_weight=None, categorical_balance=None):
        n = len(data)
        spatial = family in MixedSearch.SPATIAL_FAMILIES
        shape = (n, data.environment.shape[1] * data.environment.shape[-1] ** 2) if spatial else (n, data.environment.shape[1])
        features = np.empty(shape, dtype=np.float32)
        for start in range(0, n, 4096):
            end = min(start + 4096, n)
            normalized = (data.environment[start:end] - mean[None, :, None, None]) / std[None, :, None, None]
            features[start:end] = normalized.reshape(end-start, -1) if spatial else normalized.mean(axis=(2, 3))
        burned = data.burned.reshape(n, -1).copy()
        burned[:, burned.shape[1] // 2] = 0.
        effective = np.asarray(data.weight if optimization_weight is None else optimization_weight, dtype=np.float64)
        if effective.shape != (n,) or not np.isfinite(effective).all() or not (effective > 0).all():
            raise ValueError("Optimization weights must be positive finite values aligned with training rows")
        weights = (effective / effective.mean()).astype(np.float32)
        return MixedSearch.TensorData(torch.from_numpy(features).to(device), torch.from_numpy(burned).to(device),
                          data.target, data.weight, torch.from_numpy(data.target).to(device),
                          torch.from_numpy(weights).to(device), np.arange(n) if common is None else common,
                          effective, categorical_balance)


    @staticmethod
    @torch.no_grad()
    def probabilities(model, tensors, batch_size=65536):
        model.eval()
        output = np.empty(len(tensors.target), dtype=np.float32)
        for start in range(0, len(output), batch_size):
            end = min(start+batch_size, len(output))
            output[start:end] = MixedSearch.cached_probability(model, tensors.features[start:end], tensors.burned[start:end]).cpu().numpy()
        if not np.isfinite(output).all() or not ((output >= 0) & (output <= 1)).all():
            raise RuntimeError("Nonfinite or out-of-range kernel predictions")
        return output


    @staticmethod
    @torch.no_grad()
    def verify_equivalence(model, data, mean, std, family, device):
        small = crop_split(data, model.kernel_size, np.arange(min(8, len(data))))
        env = torch.from_numpy(small.environment.copy()).to(device)
        env = (env - torch.tensor(mean, device=device)[None,:,None,None]) / torch.tensor(std, device=device)[None,:,None,None]
        burned = torch.from_numpy(small.burned.copy()).to(device)
        model.eval()
        features = env.flatten(1) if family in MixedSearch.SPATIAL_FAMILIES else env.mean((2,3))
        cached = MixedSearch.cached_probability(model, features, burned.flatten(1))
        public_center = center_probability(model, env, burned)
        c = model.kernel_size // 2
        grid_center = model(burned, env).probability[:,0,c,c]
        device_error = float(torch.max(torch.abs(cached-grid_center)).cpu())
        if not torch.allclose(cached, public_center, atol=2e-6, rtol=2e-5) or not torch.allclose(cached, grid_center, atol=2e-6, rtol=2e-5):
            raise AssertionError(f"Cached/public model mismatch: {device_error}")
        reference = copy.deepcopy(model).cpu().double().eval()
        x, b = env.cpu().double(), burned.cpu().double()
        f = x.flatten(1) if family in MixedSearch.SPATIAL_FAMILIES else x.mean((2,3))
        exact = MixedSearch.cached_probability(reference, f, b.flatten(1))
        grid = reference(b,x).probability[:,0,c,c]
        error = float((exact-grid).abs().max())
        if not torch.allclose(exact, grid, atol=1e-12, rtol=1e-12):
            raise AssertionError(f"Float64 cached/public model mismatch: {error}")
        return dict(device_float32_max_error=device_error, cpu_float64_max_error=error)


    @staticmethod
    def make_contract(candidate, metadata, protocol):
        k = candidate["kernel_size"]
        contract = dict(format_version=1, architecture=("MixedNonnegativeKernel" if candidate["family"]=="mixed" else "EnvironmentConditionedConvolution" if candidate["family"]=="legacy" else "LearnedNonnegativeKernel"),
                        in_channels=len(metadata["channels"]), channels=metadata["channels"], kernel_size=k,
                        hidden_channels=candidate["hidden_channels"], dt_hours=1., center_rate=0.,
                        eligibility="at_least_one_burned_neighbor", target=protocol["target"],
                        kernel_constraint="nonnegative", output_link="one_hour_exponential", evaluation_grouping="pooled_countries",
                        population_condition=f"Known currently unburned target with complete K={k} context and at least one already-burned neighbor",
                        normalization="Continuous channels use training-only native K-contact population-weighted moments; one-hot channels retain raw 0/1 with mean=0 and scale=1",
                        event_ids=metadata["event_ids"], splits=metadata["splits"],
                        cache_metadata_sha256=protocol["cache_sha256"]["metadata.json"])
        if candidate["family"] == "mixed":
            contract["kernel_model"] = {key:candidate[key] for key in
                ("kernel_sizes", "branch_architecture", "hidden_channels", "depth", "dropout", "mixing_constraint")}
            contract["mixing"] = "Global nonnegative weights; unrestricted sum; branch rates combined before one exponential"
        elif candidate["family"] != "legacy":
            contract["kernel_model"] = {"architecture":candidate["family"], "hidden_channels":candidate["hidden_channels"],
                                       "depth":candidate["depth"], "dropout":candidate["dropout"]}
        contract["categorical_balance_settings"] = protocol.get("categorical_balance_settings", validate_categorical_balance_settings())
        contract.update(MixedSearch.split_contract_fields(metadata))
        contract.update({key:metadata[key] for key in SCHEMA_KEYS if key in metadata})
        return contract


    @staticmethod
    def parameter_sha256(model):
        """Hash ordered parameter values to verify paired variant initialization."""
        digest = hashlib.sha256()
        for name, value in model.state_dict().items():
            array = value.detach().cpu().contiguous().numpy()
            digest.update(name.encode("utf-8"))
            digest.update(str(array.dtype).encode("ascii"))
            digest.update(str(array.shape).encode("ascii"))
            digest.update(array.tobytes())
        return digest.hexdigest()


    @staticmethod
    def fit_candidate(candidate, train_data, validation_data, tensors, validation_tensors,
                      mean, std, global_baseline, metadata, protocol, output, device, epochs):
        scheduler = validate_scheduler(candidate["scheduler"])
        if scheduler["horizon"] != protocol["finalist_epochs"]:
            raise ValueError("Candidate scheduling horizon must equal the frozen finalist epoch budget")
        if not 1 <= epochs <= scheduler["horizon"]:
            raise ValueError("Training endpoint must lie inside the frozen scheduling horizon")
        MixedSearch.validate_categorical_normalization(mean, std, metadata)
        balance_audit = MixedSearch.bind_tensor_balance(train_data, metadata, protocol, output, tensors, device)
        folder = output / "candidates" / candidate["id"]
        folder.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(protocol["seed"])
        if device.type == "mps":
            torch.mps.manual_seed(protocol["seed"])
        model = MixedSearch.build(candidate, len(metadata["channels"]), device)
        (initialize_mixed_kernel_rate if isinstance(model, MixedNonnegativeKernel) else initialize_kernel_rate)(model, max(global_baseline["per_neighbor_rate_per_hour"], 1e-8))
        initial_parameter_sha256 = MixedSearch.parameter_sha256(model)
        optimizer = torch.optim.AdamW(model.parameters(), lr=candidate["learning_rate"], weight_decay=candidate["weight_decay"])
        history_path, last_path = folder / "history.json", folder / "last.pt"
        history = []
        best_score = math.inf
        if last_path.exists():
            saved = torch.load(last_path, map_location=device, weights_only=True)
            if saved.get("candidate") != candidate or saved.get("device") != str(device):
                raise ValueError("Resume requires the same candidate configuration and training device")
            if saved.get("categorical_balance") != balance_audit:
                raise ValueError("Resume categorical balancing differs from the committed optimization weights")
            if saved.get("initial_parameter_sha256") != initial_parameter_sha256:
                raise ValueError("Fresh seeded initialization differs from the resumable candidate")
            model.load_state_dict(saved["model_state_dict"])
            optimizer.load_state_dict(saved["optimizer_state_dict"])
            history = json.loads(history_path.read_text())[:saved["epoch"]]
            if len(history) != saved["epoch"] or any(
                    row.get("optimizer_step") != index or row.get("learning_rate") != learning_rate_at_step(candidate["learning_rate"], index, scheduler)
                    for index, row in enumerate(history, 1)):
                raise ValueError("Resume history differs from the committed learning-rate trajectory")
            best_score = saved["best_validation_brier"]
            # Recover the last committed best checkpoint even if interruption
            # occurred between a subsequent best save and the next state snapshot.
            torch.save(saved["best_checkpoint"], folder / "checkpoint.pt")
            torch.set_rng_state(saved["cpu_rng_state"].cpu())
            if device.type == "mps":
                torch.mps.set_rng_state(saved["mps_rng_state"].cpu())
            if device.type == "cuda":
                torch.cuda.set_rng_state_all([s.cpu() for s in saved["cuda_rng_states"]])
        contract = MixedSearch.make_contract(candidate, metadata, protocol)
        contract["categorical_balance"] = balance_audit
        verification = MixedSearch.verify_equivalence(model, train_data, mean, std, candidate["family"], device)
        prevalence = float(np.sum(train_data.weight*train_data.target)/np.sum(train_data.weight))
        optimization_prevalence = float(np.dot(tensors.optimization_weight, train_data.target) / tensors.optimization_weight.sum())
        if not 0 < optimization_prevalence < 1:
            raise ValueError("Optimization requires positive and negative native training targets")
        started = time.perf_counter()
        start_epoch = len(history)
        for epoch in range(start_epoch+1, epochs+1):
            learning_rate = learning_rate_at_step(candidate["learning_rate"], epoch, scheduler)
            for parameter_group in optimizer.param_groups:
                parameter_group["lr"] = learning_rate
            model.train()
            optimizer.zero_grad(set_to_none=True)
            # Chunked backward implements ONE full-batch optimizer step per epoch.
            # It reduces activation memory while retaining the fitted categorical optimization weights.
            loss_value = 0.
            n = len(train_data)
            for start in range(0,n,65536):
                end = min(start+65536,n)
                p = MixedSearch.cached_probability(model,tensors.features[start:end],tensors.burned[start:end])
                loss = (tensors.loss_weight[start:end]*(p-tensors.target_tensor[start:end]).square()).sum()/(n*optimization_prevalence)
                loss.backward()
                loss_value += float(loss.detach().cpu())
            gradient_norm = nn.utils.clip_grad_norm_(model.parameters(), max_norm=10., error_if_nonfinite=True)
            optimizer.step()
            p_train, p_val = MixedSearch.probabilities(model,tensors), MixedSearch.probabilities(model,validation_tensors)
            train_brier = brier(train_data.target,p_train,train_data.weight)
            optimization_train_brier = brier(train_data.target,p_train,tensors.optimization_weight)
            tc = tensors.common
            train_common_brier = brier(train_data.target[tc],p_train[tc],train_data.weight[tc])
            native_brier = brier(validation_data.target,p_val,validation_data.weight)
            ci = validation_tensors.common
            common_brier = brier(validation_data.target[ci],p_val[ci],validation_data.weight[ci])
            improved = common_brier < best_score
            if improved:
                best_score = common_brier
                checkpoint = dict(contract=contract,model_state_dict=model.state_dict(), normalization_mean=torch.from_numpy(mean.copy()),
                                  normalization_std=torch.from_numpy(std.copy()),best_epoch=epoch,validation_brier=best_score,
                                  configuration=candidate,global_rate_baseline=global_baseline,train_weighted_prevalence=prevalence,
                                  optimization_weighted_prevalence=optimization_prevalence,
                                  initial_parameter_sha256=initial_parameter_sha256,optimizer_step=epoch,learning_rate=learning_rate)
                torch.save(checkpoint,folder/"checkpoint.pt")
            record = dict(epoch=epoch,optimizer_step=epoch,learning_rate=learning_rate,
                          train_brier=train_brier,train_common_brier=train_common_brier,validation_native_brier=native_brier,
                          validation_common_brier=common_brier,training_regularized_dropout_loss=loss_value,
                          optimization_weighted_prevalence=optimization_prevalence,population_weighted_prevalence=prevalence,
                          optimization_train_brier=optimization_train_brier,
                          gradient_norm=float(gradient_norm.cpu()),parameter_norm=math.sqrt(sum(float(p.detach().square().sum().cpu()) for p in model.parameters())),
                          selected=improved,elapsed_seconds=time.perf_counter()-started)
            if isinstance(model, MixedNonnegativeKernel):
                record["mixing_weights"] = model.mixing_weights().detach().cpu().tolist()
            history.append(record)
            if epoch%32==0 or epoch==epochs:
                write_json(history_path,history)
                state = dict(model_state_dict=model.state_dict(),optimizer_state_dict=optimizer.state_dict(),epoch=epoch,
                             best_validation_brier=best_score,cpu_rng_state=torch.get_rng_state(),candidate=candidate,device=str(device),
                             categorical_balance=balance_audit,
                             initial_parameter_sha256=initial_parameter_sha256,scheduler=scheduler,next_optimizer_step=epoch+1,
                             best_checkpoint=torch.load(folder/"checkpoint.pt", map_location="cpu", weights_only=True))
                if device.type=="mps":state["mps_rng_state"]=torch.mps.get_rng_state()
                if device.type=="cuda":state["cuda_rng_states"]=torch.cuda.get_rng_state_all()
                torch.save(state,last_path)
                print(f"{candidate['id']} epoch={epoch}/{epochs} train={train_brier:.7f} val_common={common_brier:.7f} best={best_score:.7f}",flush=True)
        selected = torch.load(folder/"checkpoint.pt",map_location=device,weights_only=True)
        model.load_state_dict(selected["model_state_dict"])
        verification["selected_checkpoint"] = MixedSearch.verify_equivalence(model,train_data,mean,std,candidate["family"],device)
        reloaded = MixedSearch.load_trained_model(folder/"checkpoint.pt",device)
        if not all(torch.equal(a,b) for a,b in zip(model.state_dict().values(),reloaded.model.state_dict().values())):
            raise AssertionError("Checkpoint parameters changed on public reload")
        summary = dict(candidate=candidate,epochs_completed=len(history),best_epoch=selected["best_epoch"],
                       validation_common_brier=best_score,checkpoint=str((folder/"checkpoint.pt").resolve()),
                       train_sample_count=len(train_data),validation_native_sample_count=len(validation_data),
                       validation_common_sample_count=len(validation_tensors.common),early_stopped=False,
                       checkpoint_sha256=MixedSearch.sha256(folder/"checkpoint.pt"),
                       trainable_parameters=sum(p.numel() for p in model.parameters()),verification=verification,
                       test_used_for_selection=False,device=str(device),initial_parameter_sha256=initial_parameter_sha256,
                       categorical_balance=balance_audit,population_weighted_prevalence=prevalence,
                       optimization_weighted_prevalence=optimization_prevalence,
                       final_learning_rate=history[-1]["learning_rate"],scheduling_horizon=scheduler["horizon"])
        if isinstance(model, MixedNonnegativeKernel):
            summary["selected_mixing_weights"] = dict(zip(map(str,model.kernel_sizes),model.mixing_weights().detach().cpu().tolist(),strict=True))
            summary["mixing_interpretation"] = "Predictive coefficients; branch scale and mixing amplitude are not separately identifiable"
        write_json(folder/"summary.json",summary)
        return summary


    @staticmethod
    def setup_from_args(args):
        return MixedSearch.setup(args.output,args.cache,args.epochs,args.finalist_epochs,args.seed,args.forest_trees,
                     learning_rates=args.learning_rates,schedules=args.schedules,warmup_epochs=args.warmup_epochs,
                     minimum_lr_factor=args.minimum_lr_factor,restart_period=args.restart_period,
                     balance_settings=balance_settings_from_args(args))


    @staticmethod
    def train_search(args):
        protocol = MixedSearch.setup_from_args(args)
        metadata = json.loads((args.cache/"metadata.json").read_text())
        train_base, validation_base = (MixedSearch.load_split(args.cache,name,metadata) for name in ("train","validation"))
        validate_partition_disjointness({"train": train_base, "validation": validation_base}, metadata)
        device = choose_device(args.device)
        torch.set_num_threads(args.threads)
        summaries = []
        balance_by_k = {}
        for k in MixedSearch.SIZES:
            ti,vi = native_indices(train_base,k),native_indices(validation_base,k)
            train_data, val_data = crop_split(train_base,k,ti),crop_split(validation_base,k,vi)
            balance_by_k[k] = MixedSearch.fit_native_balance(train_data, metadata, protocol, args.output)
            effective, balance_audit = balance_by_k[k]
            mean,std = fit_normalization(train_data, metadata=metadata)
            global_baseline = fit_global_rate(train_data)
            tci = np.flatnonzero(np.isin(ti,common_indices(train_base)))
            ci = np.flatnonzero(np.isin(vi,common_indices(validation_base)))
            for spatial in (False,True):
                family = "legacy" if spatial else "mlp"
                tensors, vt = MixedSearch.tensor_data(train_data,mean,std,family,device,tci,optimization_weight=effective,categorical_balance=balance_audit),MixedSearch.tensor_data(val_data,mean,std,family,device,ci)
                for candidate in [c for c in protocol["candidates"] if c["kernel_size"]==k and ((c["family"] in MixedSearch.SPATIAL_FAMILIES)==spatial)]:
                    summary_path=args.output/"candidates"/candidate["id"]/"summary.json"
                    if summary_path.exists() and json.loads(summary_path.read_text())["epochs_completed"]>=args.epochs:
                        existing = json.loads(summary_path.read_text())
                        if existing["candidate"] != candidate or existing["device"] != str(device):
                            raise ValueError("Resume requires the same candidate configuration and training device")
                        if existing.get("categorical_balance") != balance_audit:
                            raise ValueError("Resume categorical balancing differs from the native training cohort")
                        summaries.append(existing)
                    else:
                        summaries.append(MixedSearch.fit_candidate(candidate,train_data,val_data,tensors,vt,mean,std,global_baseline,metadata,protocol,args.output,device,args.epochs))
                    write_json(args.output/"candidate_selection.json",summaries)
                del tensors,vt
                if device.type=="mps":torch.mps.empty_cache()
            del train_data,val_data
        frozen_finalists=args.output/"finalist_selection.json"
        if frozen_finalists.exists():
            before_extension=json.loads(frozen_finalists.read_text())["selection_before_extension"]
            candidates_by_id={s["candidate"]["id"]:s for s in summaries}
            finalists=[candidates_by_id[s["candidate"]["id"]] for s in before_extension]
        else:
            finalists = [min((s for s in summaries if s["candidate"]["family"]==family),key=lambda s:s["validation_common_brier"]) for family in MixedSearch.NEURAL_FAMILIES]
            write_json(frozen_finalists,dict(selection_before_extension=finalists,test_used_for_selection=False))
        for selected in finalists:
            c=selected["candidate"];k=c["kernel_size"]
            ti,vi=native_indices(train_base,k),native_indices(validation_base,k)
            td,vd=crop_split(train_base,k,ti),crop_split(validation_base,k,vi)
            effective, balance_audit = balance_by_k[k]
            mean,std=fit_normalization(td, metadata=metadata);baseline=fit_global_rate(td)
            ci=np.flatnonzero(np.isin(vi,common_indices(validation_base)))
            tci=np.flatnonzero(np.isin(ti,common_indices(train_base)))
            tensors,vt=MixedSearch.tensor_data(td,mean,std,c["family"],device,tci,optimization_weight=effective,categorical_balance=balance_audit),MixedSearch.tensor_data(vd,mean,std,c["family"],device,ci)
            extended=MixedSearch.fit_candidate(c,td,vd,tensors,vt,mean,std,baseline,metadata,protocol,args.output,device,args.finalist_epochs)
            summaries=[extended if s["candidate"]["id"]==c["id"] else s for s in summaries]
            write_json(args.output/"candidate_selection.json",summaries)
            del tensors,vt,td,vd
            if device.type=="mps":torch.mps.empty_cache()
        write_json(args.output/"neural_complete.json",dict(completed=True,candidates=len(summaries),long_finalists=len(finalists),test_used_for_selection=False))
        MixedSearch.write_learning_rate_comparisons(args.output, protocol, summaries)


    @staticmethod
    def write_learning_rate_comparisons(output, protocol, summaries):
        """Compare rates/schedules at the same first-stage budget and seeded start.

        A continued finalist's later validation outcomes are excluded from this
        comparison so they cannot acquire an unequal 4,096-versus-512 advantage.
        Final model selection can still use the entire authorized trajectory.
        """
        rows = []
        initial_hashes = {}
        for summary in summaries:
            candidate = summary["candidate"]
            base = candidate["base_configuration_id"]
            hashes = initial_hashes.setdefault(base, set())
            hashes.add(summary["initial_parameter_sha256"])
            if len(hashes) != 1:
                raise AssertionError(f"Rate/schedule variants have different initial parameters: {base}")
            history = json.loads((output/"candidates"/candidate["id"]/"history.json").read_text())
            first = history[:protocol["candidate_epochs"]]
            if len(first) != protocol["candidate_epochs"]:
                raise ValueError(f"Incomplete first-stage history: {candidate['id']}")
            best = min(first, key=lambda r: r["validation_common_brier"])
            rows.append(dict(base_configuration_id=base,candidate_id=candidate["id"],family=candidate["family"],
                             kernel_size=candidate["kernel_size"],hidden_channels=candidate["hidden_channels"],
                             depth=candidate["depth"],dropout=candidate["dropout"],weight_decay=candidate["weight_decay"],
                             peak_learning_rate=candidate["learning_rate"],schedule=candidate["scheduler"]["name"],
                             compared_epochs=len(first),best_epoch=best["epoch"],
                             validation_common_brier=best["validation_common_brier"],
                             final_validation_common_brier=first[-1]["validation_common_brier"],
                             final_train_common_brier=first[-1]["train_common_brier"],
                             final_learning_rate=first[-1]["learning_rate"],
                             initial_parameter_sha256=summary["initial_parameter_sha256"],test_used_for_selection=False))
        write_json(output/"learning_rate_comparison.json",dict(compared_epochs=protocol["candidate_epochs"],
                   interpretation="Validation-only matched first-stage budgets and identical initialization within each architecture/kernel/regularization setting; nominal AdamW decay is fixed but integrated shrinkage changes with rate trajectory",
                   test_used_for_selection=False,rows=rows))
        with (output/"learning_rate_comparison.csv").open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        return rows


    @staticmethod
    def forest_search(args):
        protocol=MixedSearch.setup_from_args(args)
        metadata=json.loads((args.cache/"metadata.json").read_text())
        train_base,val_base=(MixedSearch.load_split(args.cache,n,metadata) for n in ("train","validation"))
        validate_partition_disjointness({"train": train_base, "validation": val_base}, metadata)
        selection=[]
        for k in (3,5):
            ti=native_indices(train_base,k)
            td=crop_split(train_base,k,ti)
            effective, balance_audit = MixedSearch.fit_native_balance(td, metadata, protocol, args.output)
            mean,std=fit_normalization(td, metadata=metadata)
            env=(td.environment-mean[None,:,None,None])/std[None,:,None,None]
            ci=common_indices(val_base)
            vd=crop_split(val_base,k,ci)
            ve=(vd.environment-mean[None,:,None,None])/std[None,:,None,None]
            best=None
            for depth in (8,15,None):
                name=f"rf{k}_depth{depth}"
                path=args.output/"forests"/f"{name}.joblib"
                path.parent.mkdir(parents=True,exist_ok=True)
                summary_path=path.with_suffix(".json")
                if summary_path.exists():
                    summary=json.loads(summary_path.read_text())
                    if summary.get("categorical_balance") != balance_audit:
                        raise ValueError("Saved forest summary categorical balancing differs from the native training cohort")
                else:
                    if path.exists():
                        # A completed forest save interrupted before its summary
                        # can be safely recovered without fitting or overwriting it.
                        model=PatchRandomForest.load(path)
                        if model.metadata.get("categorical_balance") != balance_audit:
                            raise ValueError("Saved forest categorical balancing differs from the native training cohort")
                    else:
                        model=PatchRandomForest(k,n_estimators=args.forest_trees,max_depth=depth,random_state=args.seed,n_jobs=args.threads)
                    start=time.perf_counter()
                    if not path.exists():model.fit(env,td.burned,td.target,effective,channel_names=metadata["channels"])
                    p=model.predict_probability(ve,vd.burned,channel_names=metadata["channels"])
                    score=brier(vd.target,p,vd.weight)
                    if not path.exists():model.save(path,metadata=dict(normalization_mean=mean.tolist(),normalization_std=std.tolist(),cache_metadata_sha256=protocol["cache_sha256"]["metadata.json"],categorical_balance=balance_audit,
                                                                        categorical_balance_settings=protocol["categorical_balance_settings"]))
                    reload=PatchRandomForest.load(path)
                    np.testing.assert_allclose(p,reload.predict_probability(ve,vd.burned,channel_names=metadata["channels"]),rtol=0,atol=1e-12)
                    summary=dict(id=name,family="random_forest",kernel_size=k,max_depth=depth,n_estimators=args.forest_trees,
                                 checkpoint=str(path.resolve()),validation_common_brier=score,train_sample_count=len(td),
                                 checkpoint_sha256=MixedSearch.sha256(path),
                                 fit_seconds=time.perf_counter()-start,test_used_for_selection=False,categorical_balance=balance_audit)
                    write_json(summary_path,summary)
                    print(f"{name} val_common={score:.7f} seconds={summary['fit_seconds']:.1f}",flush=True)
                selection.append(summary)
                if best is None or summary["validation_common_brier"]<best["validation_common_brier"]:best=summary
            del env,ve,td,vd
        write_json(args.output/"forest_selection.json",selection)
        write_json(args.output/"forests_complete.json",dict(completed=True,candidates=len(selection),test_used_for_selection=False))


    @staticmethod
    def thresholds(data,p,indices):
        return {name:select_classification_threshold(data.target[indices],p[indices],data.weight[indices],criterion=name) for name in ("f1","mcc")}


    @staticmethod
    def finalize(args):
        if not all((args.output/name).exists() for name in ("neural_complete.json","forests_complete.json")):
            raise ValueError("Neural and forest searches must finish before test evaluation")
        protocol=MixedSearch.setup_from_args(args)
        MixedSearch.verify_protocol(protocol,args.cache)
        metadata=json.loads((args.cache/"metadata.json").read_text())
        summaries=json.loads((args.output/"candidate_selection.json").read_text())
        forests=json.loads((args.output/"forest_selection.json").read_text())
        MixedSearch.verify_balance_reports(args.output, protocol, summaries + forests)
        selected=[]
        for family in ("constant","linear",*MixedSearch.NEURAL_FAMILIES):
            for k in ((max(MixedSearch.MIXED_SIZES),) if family=="mixed" else MixedSearch.SIZES):
                selected.append(min((s for s in summaries if s["candidate"]["family"]==family and s["candidate"]["kernel_size"]==k),key=lambda s:s["validation_common_brier"]))
        for k in (3,5):selected.append(min((s for s in forests if s["kernel_size"]==k),key=lambda s:s["validation_common_brier"]))
        best=min(selected,key=lambda s:s["validation_common_brier"])
        for record in selected:
            if record.get("checkpoint_sha256") != MixedSearch.sha256(record["checkpoint"]):
                raise ValueError(f"Selected checkpoint integrity mismatch: {record['checkpoint']}")
            MixedSearch.verify_checkpoint_balance(record)
        write_json(args.output/"selection.json",dict(selected=selected,best=best,test_used_for_selection=False))
        write_json(args.output/"best_models.json",{name:record for record in selected for name in [
            f"{record['candidate']['family']}_k{record['candidate']['kernel_size']}" if "candidate" in record
            else f"random_forest_k{record['kernel_size']}"]})
        # This is the first stage loading test inputs/outcomes.
        metrics={};calibration_thresholds={};identities={}
        for split in ("validation","test","train"):
            data=MixedSearch.load_split(args.cache,split,metadata)
            identities[split] = cell_hour_identities(data)
            common=common_indices(data)
            payload=cohort_payload(data,common)
            native_cohorts={k:native_indices(data,k) for k in MixedSearch.SIZES}
            rows={}
            for record in selected:
                if "candidate" in record:
                    c=record["candidate"];name=c["id"];k=c["kernel_size"]
                    fitted=MixedSearch.load_trained_model(record["checkpoint"],args.device)
                    cropped=crop_split(data,k)
                    mean=fitted.mean[:,0,0].cpu().numpy();std=fitted.std[:,0,0].cpu().numpy()
                    tensors=MixedSearch.tensor_data(cropped,mean,std,c["family"],choose_device(args.device))
                    p=MixedSearch.probabilities(fitted.model,tensors)
                    no_contact=cropped.neighbor_count==0
                    if not np.all(p[no_contact]==0):raise AssertionError("Kernel no-contact probabilities must be structural zeros")
                    coverage=dict(predicted_count=len(p),no_contact_count=int(no_contact.sum()),no_contact_probability_max=float(p[no_contact].max()) if no_contact.any() else None)
                    del tensors,fitted
                else:
                    name=record["id"];k=record["kernel_size"]
                    fitted=PatchRandomForest.load(resolve_recorded_path(record["checkpoint"]))
                    preprocessing=fitted.metadata
                    mean=np.array(preprocessing["normalization_mean"],dtype=np.float32);std=np.array(preprocessing["normalization_std"],dtype=np.float32)
                    cropped=crop_split(data,k)
                    p=np.empty(len(data),dtype=np.float64)
                    for start in range(0,len(data),8192):
                        end=min(start+8192,len(data));e=(cropped.environment[start:end]-mean[None,:,None,None])/std[None,:,None,None]
                        p[start:end]=fitted.predict_probability(e,cropped.burned[start:end],channel_names=metadata["channels"])
                    coverage=dict(predicted_count=len(p),no_contact_count=int((cropped.neighbor_count==0).sum()),no_contact_probability_max=float(p[cropped.neighbor_count==0].max()) if (cropped.neighbor_count==0).any() else None)
                ni=native_cohorts[k]
                if split=="validation":
                    reproduced=brier(data.target[common],p[common],data.weight[common])
                    if not math.isclose(reproduced,record["validation_common_brier"],rel_tol=0,abs_tol=2e-6):
                        raise AssertionError(f"Selected checkpoint validation score mismatch: {name}")
                    calibration_thresholds[name]={"common":MixedSearch.thresholds(data,p,common),"native":MixedSearch.thresholds(data,p,ni)}
                t=calibration_thresholds[name]
                rows[name]=dict(kernel_size=k,coverage=coverage,
                                native=probability_metrics_with_all(data.target[ni],p[ni],data.weight[ni],cropped.neighbor_count[ni],thresholds=t["native"]),
                                common=probability_metrics_with_all(data.target[common],p[common],data.weight[common],cropped.neighbor_count[common],thresholds=t["common"]))
                rows[name]["categorical_groups"] = {
                    "native": categorical_group_metrics(cropped, p, metadata, indices=ni),
                    "common": categorical_group_metrics(cropped, p, metadata, indices=common),
                }
                rows[name]["native"]["calibration"]=weighted_calibration(data.target[ni],p[ni],data.weight[ni])
                rows[name]["common"]["calibration"]=weighted_calibration(data.target[common],p[common],data.weight[common])
                payload[name]=p[common]
                dest=args.output/"predictions"/split;dest.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(dest/f"{name}.npz",p=p,source_index=np.arange(len(data)),native_index=ni,common_index=common)
            dest=args.output/"predictions";dest.mkdir(exist_ok=True)
            np.savez_compressed(dest/f"{split}_common.npz",**payload)
            metrics[split]=dict(common_cohort=cohort_summary(data,common,3),native_cohorts={str(k):cohort_summary(data,native_cohorts[k],k) for k in MixedSearch.SIZES},models=rows)
            write_json(args.output/"metrics.json",metrics)
            del data
        write_json(args.output/"classification_thresholds.json",calibration_thresholds)
        partition_verification = validate_partition_disjointness(identities, metadata)
        write_json(args.output/"partition_verification.json", partition_verification)
        MixedSearch.report(args.output,protocol,selected,best,metrics)
        MixedSearch.verify_protocol(protocol,args.cache)
        write_json(args.output/"complete.json",dict(completed=True,neural_candidates=len(summaries),forest_candidates=len(forests),evaluated_models=len(selected),
                                                  test_used_for_selection=False,cache_sha256_verified={n:MixedSearch.sha256(args.cache/n)==v for n,v in protocol["cache_sha256"].items()}))


    @staticmethod
    def report(output,protocol,selected,best,metrics):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        def label(s):
            c=s.get("candidate",s)
            if c.get("family") == "mixed":
                return "mixed (" + ", ".join(f"{k}x{k}" for k in c["kernel_sizes"]) + ")"
            return f"{c.get('family')} {c['kernel_size']}x{c['kernel_size']}"
        def name(s):return s.get("candidate",s)["id"]
        def fmt(v):return f"{v:.6f}" if isinstance(v,(float,int)) else str(v)
        partition_description = MixedSearch.split_description(protocol)
        rate_text = ", ".join(f"{value:g}" for value in protocol["learning_rates"])
        schedule_text = ", ".join(protocol["schedules"])
        lines=["# Fresh single-scale and mixed-kernel scheduling search", "",f"Validation selected **{label(best)}** among the searched configurations. All test scores below were computed after selection.","",
               partition_description,"",MixedSearch.balance_description(protocol),"",
               "The target is a currently unburned cell becoming burned at exactly the next hourly snapshot. Contact uses the reconstructed current cumulative burned-area map; it does not mean an actively flaming cell.","",
               f"Every candidate completed {protocol['candidate_epochs']} full-batch epochs. One validation-selected candidate in each of five neural families continued, with optimizer and RNG state, to {protocol['finalist_epochs']} epochs. There was no early stopping. A saved prediction checkpoint can occur before the final epoch because selection minimizes validation Brier over the entire trajectory.","",
               "All fits are fresh. Constant kernels learn offset-specific rates; linear kernels map per-channel environmental patch means to nonnegative rates; MLP and residual MLP families use the same patch means; the existing CNN and new regularized CNN preserve full spatial environmental patches. Every kernel fixes its center to zero and computes q=1-exp(-sum(nonnegative offset rate × current burned neighbor)). Random forests are separate probability-classifier baselines, not learned rate kernels.","",
               "Training uses native K-contact rows from one frozen 9x9 sample cache and its original inverse inclusion weights. Native evaluation also uses K-contact. The matched comparison uses the exact same current 3x3-contact rows for every model, retaining the original weights. No-contact predictions are saved for every model; neural kernels return a valid structural zero, and forests may return nonzero probabilities.","",
               f"Optimization is AdamW with full-batch categorical optimization-weighted Brier divided by optimization-weighted training prevalence, weight decay, optional dropout, and gradient norm clipping at 10. An epoch is one pass over every native training row and ONE optimizer step, with chunked gradient accumulation. The ten single-scale architecture/regularization settings at four kernel sizes and three mixed CNN settings (widths 16, 32, 64) are each crossed with peak learning rates **{rate_text}** and schedules **{schedule_text}**, giving {len(protocol['candidates'])} kernel candidates. Width, depth, dropout, and weight decay retain the prior joint search settings. The learning-rate/schedule subgrid is fully crossed; the architecture search remains finite and joint.","",
               f"The fixed scheduling horizon is **{protocol['scheduling_horizon']} optimizer steps from the start of every candidate**, even when its initial fit stops after {protocol['candidate_epochs']} steps. Continuing a finalist restores its AdamW and RNG states and resumes the original schedule. It does not start warmup again or rebase the cosine schedule. Warmup lasts {protocol['warmup_epochs']} steps; the rate floor is {protocol['minimum_lr_factor']:g} times the peak; optional restart cycles last {protocol['restart_period']} steps. The rate actually used is saved at every epoch as `learning_rate`, with a one-based `optimizer_step`.","",
               "Constant schedules always use the peak. Linear warmup uses peak × step / warmup_length. For a nonzero warmup, ordinary cosine uses floor + (peak − floor) × (1 + cos(π × (step − warmup_length)/(horizon − warmup_length)))/2 after warmup and reaches the floor at the fixed horizon. Without warmup its cosine progress is (step − 1)/(horizon − 1). Restart schedules use cycles with progress 0/(period − 1), …, (period − 1)/(period − 1) after warmup, then restart at the peak. Scheduling never consults validation or test scores.","",
               "Every variant of the same kernel/architecture/regularization setting shares its initial parameter checksum and random seed. AdamW's nominal weight-decay coefficient stays fixed within each comparison, but its per-step shrinkage multiplier is 1 − learning_rate × weight_decay, so changing rates or schedules also changes integrated parameter shrinkage. The controlled comparison below therefore measures the complete optimizer policy at fixed nominal regularization. It does not isolate learning rate from accumulated weight decay.","",
               "## Matched test comparison", "", "| Model | Completed / selected epoch | Validation Brier | Test Brier | AP | ROC AUC | Exact NLL | F1 at validation threshold | MCC at validation threshold |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        csv_rows=[]
        for s in sorted(selected,key=lambda s:s["validation_common_brier"]):
            n=name(s);m=metrics["test"]["models"][n]["common"]
            epoch=f"{s['epochs_completed']} / {s['best_epoch']}" if "epochs_completed" in s else "trees"
            policy = f"; peak={s['candidate']['learning_rate']:g}, {s['candidate']['scheduler']['name']}" if "candidate" in s else ""
            lines.append(f"| {label(s)}{policy} | {epoch} | {fmt(s['validation_common_brier'])} | {fmt(m['brier'])} | {fmt(m['average_precision'])} | {fmt(m['roc_auc'])} | {fmt(m['exact_negative_log_likelihood_mean'])} | {fmt(m['f1_at_validation_f1_threshold'])} | {fmt(m['mcc_at_validation_mcc_threshold'])} |")
            csv_rows.append(dict(model=n,label=label(s),validation_brier=s["validation_common_brier"],**{key:value for key,value in m.items() if not isinstance(value,(list,dict))}))
        lines += ["", "## Cohort sizes", "", "| Split | Full prediction rows | 3x3 contact | 5x5 contact | 7x7 contact | 9x9 contact | Matched positives |", "|---|---:|---:|---:|---:|---:|---:|"]
        for split in ("train","validation","test"):
            c=metrics[split];lines.append(f"| {split} | {c['common_cohort']['base_sample_count']} | " + " | ".join(str(c["native_cohorts"][str(k)]["sample_count"]) for k in MixedSearch.SIZES)+f" | {c['common_cohort']['positive_sample_count']} |")
        lines += ["", "## Native test comparison", "", "These scores use different K-contact populations and therefore cannot rank kernel sizes fairly. Compare model families within the same K, or use the matched table above.","", "| Model | Native test Brier | Native AP | Native ROC AUC |", "|---|---:|---:|---:|"]
        for s in selected:
            m=metrics["test"]["models"][name(s)]["native"]
            lines.append(f"| {label(s)} | {fmt(m['brier'])} | {fmt(m['average_precision'])} | {fmt(m['roc_auc'])} |")
        comparisons=json.loads((output/"learning_rate_comparison.json").read_text())["rows"]
        lines += ["", "## Controlled learning-rate and schedule comparison", "",
                  f"Each row below fixes kernel size, architecture, dropout, weight decay, training rows, normalization, initialization, and seed. Every entry is its minimum matched validation Brier through the same first {protocol['candidate_epochs']} steps. Later finalist outcomes are excluded from this table. Full candidate trajectories and end-of-budget values are in `learning_rate_comparison.csv` and `history.json`.","",
                  "| Fixed base configuration | " + " | ".join(f"{rate:g} {schedule}" for rate in protocol["learning_rates"] for schedule in protocol["schedules"]) + " |",
                  "|---|" + "---:|"*(len(protocol["learning_rates"])*len(protocol["schedules"]))]
        for base in dict.fromkeys(row["base_configuration_id"] for row in comparisons):
            variant={(row["peak_learning_rate"],row["schedule"]):row for row in comparisons if row["base_configuration_id"]==base}
            lines.append(f"| {base} | " + " | ".join(fmt(variant[(rate,schedule)]["validation_common_brier"]) for rate in protocol["learning_rates"] for schedule in protocol["schedules"]) + " |")
        summaries=json.loads((output/"candidate_selection.json").read_text())
        by_id={name(row):row for row in summaries}
        finalists=json.loads((output/"finalist_selection.json").read_text())["selection_before_extension"]
        finalists=[by_id[name(row)] for row in finalists]
        plot_rows=math.ceil(len(MixedSearch.NEURAL_FAMILIES)/2)
        fig,axes=plt.subplots(plot_rows,2,figsize=(13,4.5*plot_rows),constrained_layout=True,squeeze=False)
        lr_fig,lr_axes=plt.subplots(plot_rows,2,figsize=(13,4.5*plot_rows),constrained_layout=True,squeeze=False)
        diagnostics={}
        for ax,lr_ax,family in zip(axes.flat,lr_axes.flat,MixedSearch.NEURAL_FAMILIES):
            s=next(row for row in finalists if row["candidate"]["family"]==family)
            h=json.loads((output/"candidates"/name(s)/"history.json").read_text())
            x=np.array([r["epoch"] for r in h]);v=np.array([r["validation_common_brier"] for r in h]);tr=np.array([r["train_common_brier"] for r in h])
            ax.plot(x,tr,label="matched training Brier");ax.plot(x,v,label="matched validation Brier")
            ax.axvline(protocol["candidate_epochs"],color="gray",linestyle=":",label="end of initial search")
            ax.scatter([s["best_epoch"]],[s["validation_common_brier"]],color="red",s=25,zorder=4,label="selected checkpoint")
            ax.set(xscale="log",xlabel="Epoch (log scale)",ylabel="Weighted Brier",title=f"{label(s)}; full {len(h)} epochs")
            ax.legend(fontsize=8)
            actual_lr=np.array([r["learning_rate"] for r in h])
            lr_ax.plot(x,actual_lr,label="actual optimizer learning rate")
            lr_ax.axvline(protocol["candidate_epochs"],color="gray",linestyle=":",label="end of initial search")
            lr_ax.set(xlabel="Optimizer step (= epoch)",ylabel="Learning rate",title=f"{label(s)}; {s['candidate']['scheduler']['name']}; peak={s['candidate']['learning_rate']:g}")
            lr_ax.legend(fontsize=8)
            early=min(v[:protocol["candidate_epochs"]]);late=min(v[protocol["candidate_epochs"]:]) if len(v)>protocol["candidate_epochs"] else None
            diagnostics[family]=dict(candidate=name(s),best_first_stage_validation_brier=float(early),best_late_validation_brier=float(late) if late is not None else None,
                                     relative_late_improvement=(float((early-late)/early) if late is not None else None),
                                     best_epoch=s["best_epoch"],final_training_brier=float(tr[-1]),minimum_training_brier=float(tr.min()),
                                     peak_learning_rate=s["candidate"]["learning_rate"],scheduler=s["candidate"]["scheduler"],
                                     initial_learning_rate=float(actual_lr[0]),final_learning_rate=float(actual_lr[-1]),
                                     interpretation="Descriptive late improvement only. " + partition_description + " No verified interpolation threshold or multi-seed grokking claim.")
        for axis in list(axes.flat)[len(MixedSearch.NEURAL_FAMILIES):] + list(lr_axes.flat)[len(MixedSearch.NEURAL_FAMILIES):]:
            axis.set_visible(False)
        mixed = next(record for record in selected if record.get("candidate", {}).get("family") == "mixed")
        mix = mixed["selected_mixing_weights"]
        lines += ["", "## Mixed kernel model", "",
                  "Independent environmental CNN branches generate nonnegative kernels at 3x3, 5x5, 7x7, and 9x9. Each branch's center coefficient is zero. Global learned nonnegative scalar coefficients have unrestricted sum. Their burned-state convolution rates are linearly combined, and one exponential converts that sum into a probability: q_i = 1 - exp(-sum_K alpha_K r_i^(K)). This is not an average of branch probabilities.", "",
                  "Mixed-model training and native evaluation use current contact within the union 9x9 support. Matched evaluation uses the same centered 3x3-contact rows as all single-scale models. Smaller branches crop the central environmental and burned patches; they remain zero when only outer-ring neighbors are burned.", "",
                  "The selected checkpoint mixing coefficients are " + ", ".join(f"alpha_{k}={value:.7g}" for k,value in mix.items()) + ". These are jointly learned predictive coefficients. Rescaling a branch kernel and inversely rescaling its coefficient preserves the combined rate, so these weights alone do not measure uniquely identifiable or causal importance of a spatial scale.", "",
                  "Mixed initialization assigns overlap-adjusted branch offset rates so the initial effective 9x9 kernel has the same uniform per-offset rate as the fitted global baseline. All branches and mixing coefficients are optimized jointly; no separately fitted branch is frozen.", ""]
        h=json.loads((output/"candidates"/name(next(s for s in finalists if s["candidate"]["family"]=="mixed"))/"history.json").read_text())
        mix_fig,mix_ax=plt.subplots(figsize=(9,4),constrained_layout=True)
        for index,k in enumerate(MixedSearch.MIXED_SIZES):
            mix_ax.plot([row["epoch"] for row in h],[row["mixing_weights"][index] for row in h],label=f"{k}x{k}")
        mix_ax.set(xlabel="Optimizer step (= epoch)",ylabel="Learned nonnegative mixing coefficient",title="Mixed finalist: global coefficients (unrestricted sum)")
        mix_ax.legend()
        mix_fig.savefig(output/"mixing_weight_curves.png",dpi=180);plt.close(mix_fig)
        lines += ["![Learned mixing coefficients](mixing_weight_curves.png)", ""]
        fig.savefig(output/"learning_curves.png",dpi=180);plt.close(fig)
        lr_fig.savefig(output/"learning_rate_curves.png",dpi=180);plt.close(lr_fig)
        write_json(output/"learning_diagnostics.json",diagnostics)
        lines += ["", "## Long-training observations", "", "![Learning curves](learning_curves.png)","",
                  "These panels show the five candidates selected for uninterrupted long training. A family/kernel winner in the test table can be a different, shorter candidate when it has a better validation checkpoint.","",
                  "![Actual optimizer learning rates](learning_rate_curves.png)","",
                  "The learning-rate panels plot rates read back from the saved per-step histories. Constant-rate controls remain available for interpreting delayed generalization without a changing learning rate. An improvement during rate decay, or after a restart, is associated with the chosen optimizer policy and alone does not establish grokking.","",
                  f"These curves show training and validation Brier under the same current 3x3-contact condition. {partition_description} Native training Brier is also saved in each history. A decrease after epoch {protocol['candidate_epochs']} is descriptive evidence of late validation improvement. Grokking requires a demonstrated memorization phase followed by delayed generalization; double descent requires a reproducible rise and subsequent fall around an interpolation regime. Neither is inferred automatically from a long run or a visually noisy curve. The references concern particular experimental settings and do not guarantee either phenomenon on reconstructed wildfire labels.","",
                  "[Grokking paper](https://arxiv.org/abs/2201.02177) and [Deep Double Descent paper](https://arxiv.org/abs/1912.02292).", ""]
        for family,d in diagnostics.items():
            lines.append(f"- {family}: best validation Brier through epoch {protocol['candidate_epochs']}={d['best_first_stage_validation_brier']:.6f}; after epoch {protocol['candidate_epochs']}={fmt(d['best_late_validation_brier'])}; selected epoch={d['best_epoch']}; minimum matched training Brier={d['minimum_training_brier']:.6f}.")
        lines += ["", "## Saved artifacts and limits", "", "`protocol.json` binds all input cache hashes, source hashes and the prespecified search. `candidate_selection.json`, `finalist_selection.json` and `selection.json` record validation-only selection. Candidate folders contain the complete per-epoch histories, selected public checkpoints and resumable final optimizer/RNG states. `predictions/` retains probabilities for all base rows and matched identities/weights. `metrics.json` retains calibration, exact and clipped NLL, Bernoulli distances, KL, AP, PR AUC, F1 and MCC. Classification thresholds are selected independently on native and matched validation populations.","",
                  "The training labels are retrospective reconstructions. Scores are inverse-inclusion-weighted sampled estimates, not exact full-grid population scores. No active-flame residence assumption was introduced. The search uses one seed and does not establish robustness, a globally best parameter setting, double descent, or grokking.", ""]
        if protocol.get("smoke_verification_only"):
            lines[2:2] = ["**EXECUTION VERIFICATION ONLY.** This short run uses a small sampled subset of the real cache and reduced epoch/tree budgets. Its numerical scores verify the pipeline and must not be used as scientific model rankings, population estimates, or evidence of grokking/double descent.", ""]
        (output/"report.md").write_text("\n".join(lines))
        fields=sorted(set().union(*(r.keys() for r in csv_rows)))
        with (output/"metrics.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(csv_rows)


    @staticmethod
    def run_all(args):
        MixedSearch.train_search(args)
        MixedSearch.forest_search(args)
        MixedSearch.finalize(args)


    @staticmethod
    def smoke(args):
        """Run every family/stage on real cache subsets with a short epoch budget."""
        source=args.cache
        if args.output==MixedSearch.DEFAULT_OUTPUT:args.output=MixedSearch.DEFAULT_SMOKE_OUTPUT
        destination=args.output/"smoke_cache"
        if not destination.exists():
            metadata=json.loads((source/"metadata.json").read_text())
            destination.mkdir(parents=True)
            rng=np.random.default_rng(args.seed)
            sampling={}
            for split in ("train","validation","test"):
                data=MixedSearch.load_split(source,split,metadata)
                count=512 if split=="train" else 256
                c3=data.burned[:,:,3:6,3:6].sum((1,2,3))>0
                c9=data.neighbor_count>0
                groups=[c3 & (data.target==label) for label in (0,1)] + [~c9 & (data.target==label) for label in (0,1)]
                indices=[]
                for mask in groups:
                    candidates=np.flatnonzero(mask)
                    indices.extend(rng.choice(candidates,min(32,len(candidates)),replace=False).tolist())
                remaining=np.setdiff1d(np.arange(len(data)),indices)
                indices=np.sort(np.r_[indices,rng.choice(remaining,count-len(indices),replace=False)]).astype(np.int64)
                payload={key:getattr(data,key)[indices] for key in CachedSplit.__dataclass_fields__}
                np.savez_compressed(destination/f"{split}.npz",**payload,original_base_index=indices)
                sampling[split]=dict(base_rows=len(data),smoke_rows=count,seed=args.seed)
            metadata.update(smoke_verification_only=True,smoke_original_cache=str(source.resolve()),smoke_sampling=sampling)
            write_json(destination/"metadata.json",metadata)
        args.cache=destination;args.epochs=2;args.finalist_epochs=4;args.forest_trees=9
        args.warmup_epochs=1;args.restart_period=2
        MixedSearch.run_all(args)


    @staticmethod
    def parser():
        p=argparse.ArgumentParser(description=MixedSearch.__doc__)
        p.add_argument("stage",choices=("run","smoke","train","forests","finalize"))
        p.add_argument("--cache",type=Path,default=MixedSearch.DEFAULT_CACHE)
        p.add_argument("--output",type=Path,default=MixedSearch.DEFAULT_OUTPUT)
        p.add_argument("--epochs",type=int,default=512)
        p.add_argument("--finalist-epochs",type=int,default=4096)
        p.add_argument("--learning-rates",type=float,nargs="+",default=list(MixedSearch.DEFAULT_LEARNING_RATES),
                       help="Peak rates crossed with every fixed kernel/architecture/regularization configuration")
        p.add_argument("--schedules",choices=SCHEDULES,nargs="+",default=list(MixedSearch.DEFAULT_SCHEDULES),
                       help="constant controls and warmup_cosine by default; optionally add warmup_cosine_restarts")
        p.add_argument("--warmup-epochs",type=int,default=32,help="Linear warmup steps for nonconstant schedules")
        p.add_argument("--minimum-lr-factor",type=float,default=.01,help="Cosine floor as a fraction of the peak learning rate")
        p.add_argument("--restart-period",type=int,default=512,help="Post-warmup optimizer steps per optional cosine restart cycle")
        p.add_argument("--seed",type=int,default=7)
        add_categorical_balance_arguments(p)
        p.add_argument("--threads",type=int,default=4)
        p.add_argument("--forest-trees",type=int,default=100)
        p.add_argument("--device",default="auto",help="auto chooses MPS, then CUDA, then CPU; resume requires same training device")
        return p


    @staticmethod
    def main():
        args=MixedSearch.parser().parse_args()
        if args.device=="auto":args.device="mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        if args.epochs<1 or args.finalist_epochs<args.epochs or args.threads<1:
            raise ValueError("Epochs/threads must be positive and finalist budget must include initial training")
        {"run":MixedSearch.run_all,"smoke":MixedSearch.smoke,"train":MixedSearch.train_search,"forests":MixedSearch.forest_search,"finalize":MixedSearch.finalize}[args.stage](args)


class MultiscaleSearch:
    """Fresh single-scale, linear mixed and neural mixed kernel searches.

    The declared partitions, labels and inverse sampling weights come from one
    frozen 9x9 cache. Each model trains on its K-contact rows. Hyperparameters,
    epochs, finalists and classification thresholds use validation only. Final
    test predictions cover every base-cache row; comparison metrics use native
    K-contact and identical 3-contact cohorts. No early stopping is used.
    """

    __doc__ = __doc__.replace("\n    ", "\n")
    __file__ = __file__
    split_contract_fields = staticmethod(Search.split_contract_fields)
    split_description = staticmethod(Search.split_description)
    fit_native_balance = staticmethod(Search.fit_native_balance)
    bind_tensor_balance = staticmethod(Search.bind_tensor_balance)
    balance_description = staticmethod(Search.balance_description)
    validate_categorical_normalization = staticmethod(Search.validate_categorical_normalization)
    verify_balance_reports = staticmethod(Search.verify_balance_reports)
    verify_checkpoint_balance = staticmethod(Search.verify_checkpoint_balance)
    PatchRandomForest = staticmethod(PatchRandomForest)
    brier = staticmethod(brier)
    probability_metrics_with_all = staticmethod(probability_metrics_with_all)
    balance_settings_from_args = staticmethod(balance_settings_from_args)
    initialize_mixed_kernel_rate = staticmethod(initialize_mixed_kernel_rate)
    initialize_neural_mixed_kernel_rate = staticmethod(initialize_neural_mixed_kernel_rate)
    load_split = staticmethod(load_split)
    TRAINING_SOURCE_FILES = CANONICAL_TRAINING_SOURCE_FILES

    RUNS = PATH_RUNS
    DEFAULT_CACHE = RUNS / "20261009_weighted_stratified_split/prepared_all"
    DEFAULT_OUTPUT = RUNS / "20261009_multiscale_kernel_search_weighted_stratified_categorical_balanced"
    DEFAULT_SMOKE_OUTPUT = RUNS / "20261009_multiscale_kernel_smoke_weighted_stratified_categorical_balanced"
    DEFAULT_LEARNING_RATES = (.001, .003, .01, .03)
    DEFAULT_SCHEDULES = ("constant", "warmup_cosine")
    SIZES = (3, 5, 7, 9)
    NEURAL_FAMILIES = ("legacy", "cnn", "mlp", "residual_mlp", "mixed", "neural_mixed")
    SPATIAL_FAMILIES = ("legacy", "cnn", "mixed", "neural_mixed")
    MIXED_SIZES = (3, 5, 7, 9)
    CACHE_FILES = ("metadata.json", "train.npz", "validation.npz", "test.npz")


    @staticmethod
    def sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


    @staticmethod
    def candidate_plan(learning_rates=DEFAULT_LEARNING_RATES, schedules=DEFAULT_SCHEDULES,
                       horizon=4096, warmup_epochs=32, minimum_lr_factor=.01, restart_period=512):
        """Cross single-scale and mixed architecture settings with rates and schedules.

        For each kernel/architecture setting, every variant receives the same seed,
        initialization, training cohort, normalization, dropout, and weight decay.
        This is a full rate-by-schedule crossing over a joint architecture search.
        """
        learning_rates = tuple(float(value) for value in learning_rates)
        schedules = tuple(schedules)
        if not learning_rates or len(set(learning_rates)) != len(learning_rates):
            raise ValueError("Learning rates must be a nonempty list without duplicates")
        if any(not math.isfinite(rate) or rate <= 0 for rate in learning_rates):
            raise ValueError("Learning rates must be finite and positive")
        if not schedules or len(set(schedules)) != len(schedules):
            raise ValueError("Schedules must be a nonempty list without duplicates")
        scheduler_configurations = [validate_scheduler(dict(name=name, horizon=horizon, warmup_epochs=warmup_epochs,
                                                           minimum_lr_factor=minimum_lr_factor, restart_period=restart_period))
                                    for name in schedules]
        configurations = [
            ("constant", 1, 1, 0., .01, 0.),
            ("linear", 1, 1, 0., .01, .0001),
            ("legacy", 16, 1, 0., .001, .0001),
            ("cnn", 32, 1, .15, .003, .001),
            ("mlp", 8, 2, 0., .003, 0.),
            ("mlp", 32, 2, .15, .003, .0001),
            ("mlp", 128, 2, .15, .003, .01),
            ("mlp", 32, 4, 0., .001, .1),
            ("residual_mlp", 32, 3, .15, .003, .001),
            ("residual_mlp", 128, 3, .15, .001, .01),
        ]
        plan = []
        for k in MultiscaleSearch.SIZES:
            for index, (family, width, depth, dropout, _, decay) in enumerate(configurations):
                base_id = f"k{k}_{family}_{index:02d}"
                for rate in learning_rates:
                    for scheduler in scheduler_configurations:
                        plan.append(dict(id=f"{base_id}_lr{rate!r}_{scheduler['name']}",
                                         base_configuration_id=base_id, kernel_size=k, family=family,
                                         hidden_channels=width, depth=depth, dropout=dropout,
                                         learning_rate=rate, weight_decay=decay, scheduler=dict(scheduler)))
        # Independent environmental CNNs at every scale; global nonnegative mixing.
        # The support is the union (maxK=9), not a separately scored single scale.
        for index, (width, dropout, decay) in enumerate(((16, 0., .0001), (32, .15, .001), (64, .15, .01))):
            base_id = f"mixed_3_5_7_9_{index:02d}"
            for rate in learning_rates:
                for scheduler in scheduler_configurations:
                    plan.append(dict(id=f"{base_id}_lr{rate!r}_{scheduler['name']}",
                                     base_configuration_id=base_id, kernel_size=max(MultiscaleSearch.MIXED_SIZES), family="mixed",
                                     kernel_sizes=list(MultiscaleSearch.MIXED_SIZES), branch_architecture="cnn",
                                     mixing_constraint="nonnegative", hidden_channels=width, depth=1, dropout=dropout,
                                     learning_rate=rate, weight_decay=decay, scheduler=dict(scheduler)))
        for index, (width, dropout, combiner_width, combiner_dropout, decay) in enumerate(
                ((16, 0., 8, 0., .0001), (32, .15, 16, .1, .001), (64, .15, 32, .15, .01))):
            base_id = f"neural_mixed_3_5_7_9_{index:02d}"
            for rate in learning_rates:
                for scheduler in scheduler_configurations:
                    plan.append(dict(id=f"{base_id}_lr{rate!r}_{scheduler['name']}",
                                     base_configuration_id=base_id, kernel_size=max(MultiscaleSearch.MIXED_SIZES), family="neural_mixed",
                                     kernel_sizes=list(MultiscaleSearch.MIXED_SIZES), branch_architecture="cnn",
                                     hidden_channels=width, depth=1, dropout=dropout,
                                     combiner_hidden_channels=combiner_width, combiner_dropout=combiner_dropout,
                                     combiner_input_transform="identity", learning_rate=rate,
                                     weight_decay=decay, scheduler=dict(scheduler)))
        return plan


    @staticmethod
    def load_trained_model(path, device="cpu"):
        """Dispatch saved inference without modifying the previous frozen loader."""
        architecture = torch.load(resolve_recorded_path(path), map_location="cpu", weights_only=True)["contract"]["architecture"]
        if architecture == "NeuralMixedNonnegativeKernel":
            return load_neural_mixed_trained_model(path, device)
        return (load_mixed_trained_model if architecture == "MixedNonnegativeKernel" else load_single_trained_model)(path, device)


    @staticmethod
    def verify_protocol(protocol, cache):
        """Reject input/code drift before resuming or exposing test outcomes."""
        if str(cache.resolve()) != protocol["cache"]:
            raise ValueError("Cache path differs from the frozen experiment protocol")
        for name, expected in protocol["cache_sha256"].items():
            if MultiscaleSearch.sha256(cache / name) != expected:
                raise ValueError(f"Cache integrity mismatch: {name}; use a new output directory for changed inputs")
        for name, expected in protocol["training_source_sha256"].items():
            if not (Path(__file__).parent / name).is_file() or MultiscaleSearch.sha256(Path(__file__).parent / name) != expected:
                raise ValueError(f"Training source integrity mismatch: {name}; use a new output directory for changed code")


    @staticmethod
    def verify_environmental_sources(metadata, local_root=None):
        """Find a complete manifest-matching source copy in this checkout or its saved root."""
        recorded_root = resolve_recorded_path(metadata["data_root"])
        if not metadata.get("source_files"):
            return recorded_root, []
        if local_root is None:
            local_root = DATA_ROOT
        failures = []
        for root in dict.fromkeys((Path(local_root).resolve(), recorded_root.resolve())):
            checked = []
            for source in metadata["source_files"]:
                actual = root / source["path"]
                if not actual.is_file() or MultiscaleSearch.sha256(actual) != source["sha256"]:
                    failures.append(str(actual))
                    break
                checked.append(source["path"])
            else:
                return root, checked
        raise ValueError("Source integrity mismatch: no complete manifest-matching environmental data copy; "
                         + "; ".join(failures))


    @staticmethod
    def setup(output, cache, epochs, finalist_epochs, seed, forest_trees=100, *,
              learning_rates=DEFAULT_LEARNING_RATES, schedules=DEFAULT_SCHEDULES,
              warmup_epochs=32, minimum_lr_factor=.01, restart_period=512, balance_settings=None):
        balance_settings = validate_categorical_balance_settings(**(balance_settings or {}))
        if epochs < 1 or finalist_epochs < epochs:
            raise ValueError("Candidate epochs must be positive and fit inside the finalist horizon")
        candidates = MultiscaleSearch.candidate_plan(learning_rates, schedules, finalist_epochs, warmup_epochs,
                                    minimum_lr_factor, restart_period)
        settings = dict(learning_rates=[float(v) for v in learning_rates], schedules=list(schedules),
                        scheduling_horizon=finalist_epochs, warmup_epochs=warmup_epochs,
                        minimum_lr_factor=float(minimum_lr_factor), restart_period=restart_period,
                        categorical_balance_settings=balance_settings)
        output.mkdir(parents=True, exist_ok=True)
        path = output / "protocol.json"
        if path.exists():
            protocol = json.loads(path.read_text())
            for key, value in {"cache": str(cache.resolve()), "candidate_epochs": epochs,
                               "finalist_epochs": finalist_epochs, "seed": seed, "forest_trees": forest_trees,
                               **settings, "candidates": candidates}.items():
                if protocol[key] != value:
                    raise ValueError(f"Resume protocol mismatch: {key}")
            MultiscaleSearch.verify_protocol(protocol, cache)
            return protocol
        metadata = json.loads((cache / "metadata.json").read_text())
        validate_split_metadata(metadata, require_all_partitions=True)
        if metadata["dt_hours"] != 1. or metadata["kernel_size"] != 9:
            raise ValueError("The experiment requires the frozen one-hour 9x9 base cache")
        hashes = {name: MultiscaleSearch.sha256(cache / name) for name in MultiscaleSearch.CACHE_FILES}
        root, source_checks = MultiscaleSearch.verify_environmental_sources(metadata)
        sources = {name: MultiscaleSearch.sha256(Path(__file__).parent / name) for name in MultiscaleSearch.TRAINING_SOURCE_FILES}
        protocol = dict(cache=str(cache.resolve()), candidate_epochs=epochs, finalist_epochs=finalist_epochs,
                        seed=seed, forest_trees=forest_trees, kernel_sizes=list(MultiscaleSearch.SIZES), candidates=candidates, **settings,
                        training="Native K-contact cells from one frozen base sampling design; complete known context; current center unburned",
                        contact="At least one off-center cell already burned at time t inside centered KxK; cumulative reconstructed burned map, not active flame",
                        common="Identical original 9x9 cache rows with contact inside centered 3x3; original labels and inverse inclusion weights",
                        selection="Minimum float64 inverse-weighted common-contact validation Brier; checkpoint and hyperparameters before test",
                        long_finalists="One globally validation-selected candidate per neural family (legacy, cnn, mlp, residual_mlp, mixed, neural_mixed), continued from last optimizer state to the full finalist epoch budget",
                        optimizer="AdamW, full-batch categorical optimization-weighted Brier/optimization prevalence, explicit prespecified rate before every optimizer step, decay on all parameters, no early stopping",
                        schedule="One-based optimizer steps; the full finalist horizon is fixed from step one, including candidates initially trained only to the candidate budget; no validation-triggered scheduling",
                        controlled_comparison="Peak rate and schedule crossed within each fixed kernel/architecture/regularization configuration, sharing initialization and seed; compare first-stage validation trajectories at identical epoch budgets",
                        weight_decay_interpretation="AdamW decay multiplies each parameter by (1-learning_rate*weight_decay) per optimizer step; equal nominal decay with different schedules does not imply equal integrated shrinkage",
                        prediction="All original base-cache rows, including no-contact inputs; neural kernel structural zero for known no-contact",
                        test_used_for_selection=False, cache_sha256=hashes, training_source_sha256=sources,
                        verified_source_files=len(source_checks), verified_data_root=str(root.resolve()),
                        target="unburned at t becomes burned at exactly t+3600s",
                        limitations=["Retrospective reconstructed hourly labels; not independent observed active flames",
                                     "Best among the finite prespecified joint configurations; not a global optimum",
                                     "Six single-seed neural finalists; curves can suggest delayed generalization, not prove grokking or double descent"],
                        versions=dict(python=platform.python_version(), numpy=np.__version__, torch=str(torch.__version__)),
                        references=["https://arxiv.org/abs/2201.02177", "https://arxiv.org/abs/1912.02292"])
        protocol["mixed_model"] = dict(kernel_sizes=list(MultiscaleSearch.MIXED_SIZES), branch_architecture="cnn",
            mixing_constraint="nonnegative", mixing="Global jointly learned softplus scalar weights with unrestricted sum",
            rate="sum_K alpha_K sum_offset kernel_K(offset) * current_burned(offset)",
            probability="1-exp(-combined_rate); one exponential after linear combination, not mixed branch probabilities",
            native_contact="9x9 union-support contact", common_contact="Identical centered 3x3 contact rows used by every model",
            identifiability="Mixing weights and branch amplitudes are not separately identifiable; weights are not causal scale importance")
        protocol["neural_mixed_model"] = dict(kernel_sizes=list(MultiscaleSearch.MIXED_SIZES), branch_architecture="cnn",
            inputs="Four raw branch convolution rates in ascending kernel-size order",
            combiner="4 -> hidden width -> 1 MLP with SiLU, optional dropout and positive zero-preserving scalar readout",
            readout="lambda=sum(raw_branch_rates)*softplus(MLP(raw_branch_rates)); one combined nonnegative rate, exact zero at all-zero inputs",
            probability="1-exp(-lambda); one exponential after neural combination",
            initialization="MLP final weights zero and inverse-softplus-one bias; initial gain is one and effective total branch rate matches global baseline",
            kernel_interpretation="The nonlinear rate depends on current burned state and cannot be represented by a burned-independent environmental kernel",
            native_contact="9x9 union support", common_contact="Identical centered 3x3 contact rows")
        protocol.update(MultiscaleSearch.split_contract_fields(metadata))
        protocol["training"] += "; split unit: " + protocol["split_unit"]
        protocol["smoke_verification_only"] = bool(metadata.get("smoke_verification_only", False))
        snapshot = output / "source_snapshot"
        snapshot.mkdir(exist_ok=True)
        for name in sources:
            (snapshot / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(__file__).parent / name, snapshot / name)
        write_json(path, protocol)
        return protocol


    @staticmethod
    def build(candidate, channels, device):
        if candidate["family"] == "neural_mixed":
            model = build_neural_mixed_kernel_model(channels, **{key:candidate[key] for key in
                ("kernel_sizes", "branch_architecture", "hidden_channels", "depth", "dropout",
                 "combiner_hidden_channels", "combiner_dropout", "combiner_input_transform")})
        elif candidate["family"] == "mixed":
            model = build_mixed_kernel_model(channels, kernel_sizes=candidate["kernel_sizes"],
                branch_architecture=candidate["branch_architecture"], hidden_channels=candidate["hidden_channels"],
                depth=candidate["depth"], dropout=candidate["dropout"], mixing_constraint=candidate["mixing_constraint"])
        elif candidate["family"] == "legacy":
            model = EnvironmentConditionedConvolution(channels, candidate["kernel_size"], candidate["hidden_channels"])
        else:
            model = build_kernel_model(channels, candidate["kernel_size"], candidate["family"],
                                       candidate["hidden_channels"], candidate["depth"], candidate["dropout"])
        return model.to(device)


    @staticmethod
    def _pointwise(layer, value):
        """Exact affine/activation computation at one spatial output position."""
        if isinstance(layer, nn.Conv2d):
            return F.linear(value, layer.weight.flatten(1), layer.bias)
        if isinstance(layer, nn.Dropout2d):
            # At spatial shape 1x1, channel dropout equals scalar feature dropout.
            return F.dropout(value, layer.p, layer.training)
        if isinstance(layer, nn.Sequential):
            for member in layer:
                value = MultiscaleSearch._pointwise(member, value)
            return value
        if hasattr(layer, "update"):
            return F.silu(value + MultiscaleSearch._pointwise(layer.update, value))
        return layer(value)


    @staticmethod
    def cached_probability(model, features, burned):
        """Trusted validated feature path retaining the public model's parameters.

        Linear rather than 1x1 convolution avoids repeated GPU validation barriers.
        The full spatial first layer is a flattened dot product. CPU float64 and
        device float32 equivalence are checked before and after every fitted run.
        Dropout has the same law at the single output position.
        """
        if isinstance(model, MixedNonnegativeKernel):
            size = model.kernel_size
            environmental_patch = features.reshape(-1, model.in_channels, size, size)
            burned_patch = burned.reshape(-1, 1, size, size)
            rates = []
            for branch in model.branches.values():
                k = branch.kernel_size
                start = (size-k)//2
                environment = environmental_patch[:, :, start:start+k, start:start+k]
                source = burned_patch[:, :, start:start+k, start:start+k].flatten(1)
                branch_features = environment.flatten(1) if branch.architecture == "cnn" else environment.mean((2,3))
                network = branch.kernel_network
                if hasattr(network, "logits"):
                    logits = network.logits.reshape(1, -1).expand(len(features), -1)
                else:
                    hidden = F.linear(branch_features, network.spatial.weight.flatten(1), network.spatial.bias)
                    logits = MultiscaleSearch._pointwise(network.output, MultiscaleSearch._pointwise(network.hidden, hidden))
                rates.append((F.softplus(logits) * branch.off_center.flatten() * source).sum(dim=1))
            raw_rates = torch.stack(rates, dim=1)
            combined = (model.combined_rate(raw_rates) if isinstance(model, NeuralMixedNonnegativeKernel)
                        else (raw_rates * model.mixing_weights()[None, :]).sum(dim=1))
            probability = -torch.expm1(-combined)
            return torch.where(burned_patch[:,0,size//2,size//2] == 1, 0, probability)
        network = model.kernel_network
        if isinstance(network, nn.Sequential):
            logits = MultiscaleSearch._pointwise(network, features)
        elif hasattr(network, "logits"):
            logits = network.logits.reshape(1, -1).expand(len(features), -1)
        else:
            hidden = F.linear(features, network.spatial.weight.flatten(1), network.spatial.bias)
            logits = MultiscaleSearch._pointwise(network.output, MultiscaleSearch._pointwise(network.hidden, hidden))
        rate = (F.softplus(logits) * burned).sum(dim=1)
        return -torch.expm1(-rate)


    @dataclass
    class TensorData:
        features: torch.Tensor
        burned: torch.Tensor
        target: np.ndarray
        weight: np.ndarray
        target_tensor: torch.Tensor
        loss_weight: torch.Tensor
        common: np.ndarray
        optimization_weight: np.ndarray | None = None
        categorical_balance: dict | None = None


    @staticmethod
    def tensor_data(data, mean, std, family, device, common=None, *,
                    optimization_weight=None, categorical_balance=None):
        n = len(data)
        spatial = family in MultiscaleSearch.SPATIAL_FAMILIES
        shape = (n, data.environment.shape[1] * data.environment.shape[-1] ** 2) if spatial else (n, data.environment.shape[1])
        features = np.empty(shape, dtype=np.float32)
        for start in range(0, n, 4096):
            end = min(start + 4096, n)
            normalized = (data.environment[start:end] - mean[None, :, None, None]) / std[None, :, None, None]
            features[start:end] = normalized.reshape(end-start, -1) if spatial else normalized.mean(axis=(2, 3))
        burned = data.burned.reshape(n, -1).copy()
        burned[:, burned.shape[1] // 2] = 0.
        effective = np.asarray(data.weight if optimization_weight is None else optimization_weight, dtype=np.float64)
        if effective.shape != (n,) or not np.isfinite(effective).all() or not (effective > 0).all():
            raise ValueError("Optimization weights must be positive finite values aligned with training rows")
        weights = (effective / effective.mean()).astype(np.float32)
        return MultiscaleSearch.TensorData(torch.from_numpy(features).to(device), torch.from_numpy(burned).to(device),
                          data.target, data.weight, torch.from_numpy(data.target).to(device),
                          torch.from_numpy(weights).to(device), np.arange(n) if common is None else common,
                          effective, categorical_balance)


    @staticmethod
    @torch.no_grad()
    def probabilities(model, tensors, batch_size=65536):
        model.eval()
        output = np.empty(len(tensors.target), dtype=np.float32)
        for start in range(0, len(output), batch_size):
            end = min(start+batch_size, len(output))
            output[start:end] = MultiscaleSearch.cached_probability(model, tensors.features[start:end], tensors.burned[start:end]).cpu().numpy()
        if not np.isfinite(output).all() or not ((output >= 0) & (output <= 1)).all():
            raise RuntimeError("Nonfinite or out-of-range kernel predictions")
        return output


    @staticmethod
    @torch.no_grad()
    def verify_equivalence(model, data, mean, std, family, device):
        small = crop_split(data, model.kernel_size, np.arange(min(8, len(data))))
        env = torch.from_numpy(small.environment.copy()).to(device)
        env = (env - torch.tensor(mean, device=device)[None,:,None,None]) / torch.tensor(std, device=device)[None,:,None,None]
        burned = torch.from_numpy(small.burned.copy()).to(device)
        model.eval()
        features = env.flatten(1) if family in MultiscaleSearch.SPATIAL_FAMILIES else env.mean((2,3))
        cached = MultiscaleSearch.cached_probability(model, features, burned.flatten(1))
        public_center = center_probability(model, env, burned)
        c = model.kernel_size // 2
        grid_center = model(burned, env).probability[:,0,c,c]
        device_error = float(torch.max(torch.abs(cached-grid_center)).cpu())
        if not torch.allclose(cached, public_center, atol=2e-6, rtol=2e-5) or not torch.allclose(cached, grid_center, atol=2e-6, rtol=2e-5):
            raise AssertionError(f"Cached/public model mismatch: {device_error}")
        reference = copy.deepcopy(model).cpu().double().eval()
        x, b = env.cpu().double(), burned.cpu().double()
        f = x.flatten(1) if family in MultiscaleSearch.SPATIAL_FAMILIES else x.mean((2,3))
        exact = MultiscaleSearch.cached_probability(reference, f, b.flatten(1))
        grid = reference(b,x).probability[:,0,c,c]
        error = float((exact-grid).abs().max())
        if not torch.allclose(exact, grid, atol=1e-12, rtol=1e-12):
            raise AssertionError(f"Float64 cached/public model mismatch: {error}")
        return dict(device_float32_max_error=device_error, cpu_float64_max_error=error)


    @staticmethod
    def make_contract(candidate, metadata, protocol):
        k = candidate["kernel_size"]
        contract = dict(format_version=1, architecture=("NeuralMixedNonnegativeKernel" if candidate["family"]=="neural_mixed" else "MixedNonnegativeKernel" if candidate["family"]=="mixed" else "EnvironmentConditionedConvolution" if candidate["family"]=="legacy" else "LearnedNonnegativeKernel"),
                        in_channels=len(metadata["channels"]), channels=metadata["channels"], kernel_size=k,
                        hidden_channels=candidate["hidden_channels"], dt_hours=1., center_rate=0.,
                        eligibility="at_least_one_burned_neighbor", target=protocol["target"],
                        kernel_constraint="nonnegative", output_link="one_hour_exponential", evaluation_grouping="pooled_countries",
                        population_condition=f"Known currently unburned target with complete K={k} context and at least one already-burned neighbor",
                        normalization="Continuous channels use training-only native K-contact population-weighted moments; one-hot channels retain raw 0/1 with mean=0 and scale=1",
                        event_ids=metadata["event_ids"], splits=metadata["splits"],
                        cache_metadata_sha256=protocol["cache_sha256"]["metadata.json"])
        if candidate["family"] == "neural_mixed":
            contract["kernel_model"] = {key:candidate[key] for key in
                ("kernel_sizes", "branch_architecture", "hidden_channels", "depth", "dropout",
                 "combiner_hidden_channels", "combiner_dropout", "combiner_input_transform")}
            contract["combination"] = "One zero-preserving nonnegative neural combined rate from four raw convolution rates before the exponential"
        elif candidate["family"] == "mixed":
            contract["kernel_model"] = {key:candidate[key] for key in
                ("kernel_sizes", "branch_architecture", "hidden_channels", "depth", "dropout", "mixing_constraint")}
            contract["mixing"] = "Global nonnegative weights; unrestricted sum; branch rates combined before one exponential"
        elif candidate["family"] != "legacy":
            contract["kernel_model"] = {"architecture":candidate["family"], "hidden_channels":candidate["hidden_channels"],
                                       "depth":candidate["depth"], "dropout":candidate["dropout"]}
        contract["categorical_balance_settings"] = protocol.get("categorical_balance_settings", validate_categorical_balance_settings())
        contract.update(MultiscaleSearch.split_contract_fields(metadata))
        contract.update({key:metadata[key] for key in SCHEMA_KEYS if key in metadata})
        return contract


    @staticmethod
    def parameter_sha256(model):
        """Hash ordered parameter values to verify paired variant initialization."""
        digest = hashlib.sha256()
        for name, value in model.state_dict().items():
            array = value.detach().cpu().contiguous().numpy()
            digest.update(name.encode("utf-8"))
            digest.update(str(array.dtype).encode("ascii"))
            digest.update(str(array.shape).encode("ascii"))
            digest.update(array.tobytes())
        return digest.hexdigest()


    @staticmethod
    def fit_candidate(candidate, train_data, validation_data, tensors, validation_tensors,
                      mean, std, global_baseline, metadata, protocol, output, device, epochs):
        scheduler = validate_scheduler(candidate["scheduler"])
        if scheduler["horizon"] != protocol["finalist_epochs"]:
            raise ValueError("Candidate scheduling horizon must equal the frozen finalist epoch budget")
        if not 1 <= epochs <= scheduler["horizon"]:
            raise ValueError("Training endpoint must lie inside the frozen scheduling horizon")
        MultiscaleSearch.validate_categorical_normalization(mean, std, metadata)
        balance_audit = MultiscaleSearch.bind_tensor_balance(train_data, metadata, protocol, output, tensors, device)
        folder = output / "candidates" / candidate["id"]
        folder.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(protocol["seed"])
        if device.type == "mps":
            torch.mps.manual_seed(protocol["seed"])
        model = MultiscaleSearch.build(candidate, len(metadata["channels"]), device)
        initializer = (initialize_neural_mixed_kernel_rate if isinstance(model, NeuralMixedNonnegativeKernel)
                       else initialize_mixed_kernel_rate if isinstance(model, MixedNonnegativeKernel) else initialize_kernel_rate)
        initializer(model, max(global_baseline["per_neighbor_rate_per_hour"], 1e-8))
        initial_parameter_sha256 = MultiscaleSearch.parameter_sha256(model)
        optimizer = torch.optim.AdamW(model.parameters(), lr=candidate["learning_rate"], weight_decay=candidate["weight_decay"])
        history_path, last_path = folder / "history.json", folder / "last.pt"
        history = []
        best_score = math.inf
        if last_path.exists():
            saved = torch.load(last_path, map_location=device, weights_only=True)
            if saved.get("candidate") != candidate or saved.get("device") != str(device):
                raise ValueError("Resume requires the same candidate configuration and training device")
            if saved.get("categorical_balance") != balance_audit:
                raise ValueError("Resume categorical balancing differs from the committed optimization weights")
            if saved.get("initial_parameter_sha256") != initial_parameter_sha256:
                raise ValueError("Fresh seeded initialization differs from the resumable candidate")
            model.load_state_dict(saved["model_state_dict"])
            optimizer.load_state_dict(saved["optimizer_state_dict"])
            history = json.loads(history_path.read_text())[:saved["epoch"]]
            if len(history) != saved["epoch"] or any(
                    row.get("optimizer_step") != index or row.get("learning_rate") != learning_rate_at_step(candidate["learning_rate"], index, scheduler)
                    for index, row in enumerate(history, 1)):
                raise ValueError("Resume history differs from the committed learning-rate trajectory")
            best_score = saved["best_validation_brier"]
            # Recover the last committed best checkpoint even if interruption
            # occurred between a subsequent best save and the next state snapshot.
            torch.save(saved["best_checkpoint"], folder / "checkpoint.pt")
            torch.set_rng_state(saved["cpu_rng_state"].cpu())
            if device.type == "mps":
                torch.mps.set_rng_state(saved["mps_rng_state"].cpu())
            if device.type == "cuda":
                torch.cuda.set_rng_state_all([s.cpu() for s in saved["cuda_rng_states"]])
        contract = MultiscaleSearch.make_contract(candidate, metadata, protocol)
        contract["categorical_balance"] = balance_audit
        verification = MultiscaleSearch.verify_equivalence(model, train_data, mean, std, candidate["family"], device)
        prevalence = float(np.sum(train_data.weight*train_data.target)/np.sum(train_data.weight))
        optimization_prevalence = float(np.dot(tensors.optimization_weight, train_data.target) / tensors.optimization_weight.sum())
        if not 0 < optimization_prevalence < 1:
            raise ValueError("Optimization requires positive and negative native training targets")
        started = time.perf_counter()
        start_epoch = len(history)
        for epoch in range(start_epoch+1, epochs+1):
            learning_rate = learning_rate_at_step(candidate["learning_rate"], epoch, scheduler)
            for parameter_group in optimizer.param_groups:
                parameter_group["lr"] = learning_rate
            model.train()
            optimizer.zero_grad(set_to_none=True)
            # Chunked backward implements ONE full-batch optimizer step per epoch.
            # It reduces activation memory while retaining the fitted categorical optimization weights.
            loss_value = 0.
            n = len(train_data)
            for start in range(0,n,65536):
                end = min(start+65536,n)
                p = MultiscaleSearch.cached_probability(model,tensors.features[start:end],tensors.burned[start:end])
                loss = (tensors.loss_weight[start:end]*(p-tensors.target_tensor[start:end]).square()).sum()/(n*optimization_prevalence)
                loss.backward()
                loss_value += float(loss.detach().cpu())
            gradient_norm = nn.utils.clip_grad_norm_(model.parameters(), max_norm=10., error_if_nonfinite=True)
            optimizer.step()
            p_train, p_val = MultiscaleSearch.probabilities(model,tensors), MultiscaleSearch.probabilities(model,validation_tensors)
            train_brier = brier(train_data.target,p_train,train_data.weight)
            optimization_train_brier = brier(train_data.target,p_train,tensors.optimization_weight)
            tc = tensors.common
            train_common_brier = brier(train_data.target[tc],p_train[tc],train_data.weight[tc])
            native_brier = brier(validation_data.target,p_val,validation_data.weight)
            ci = validation_tensors.common
            common_brier = brier(validation_data.target[ci],p_val[ci],validation_data.weight[ci])
            improved = common_brier < best_score
            if improved:
                best_score = common_brier
                checkpoint = dict(contract=contract,model_state_dict=model.state_dict(), normalization_mean=torch.from_numpy(mean.copy()),
                                  normalization_std=torch.from_numpy(std.copy()),best_epoch=epoch,validation_brier=best_score,
                                  configuration=candidate,global_rate_baseline=global_baseline,train_weighted_prevalence=prevalence,
                                  optimization_weighted_prevalence=optimization_prevalence,
                                  initial_parameter_sha256=initial_parameter_sha256,optimizer_step=epoch,learning_rate=learning_rate)
                torch.save(checkpoint,folder/"checkpoint.pt")
            record = dict(epoch=epoch,optimizer_step=epoch,learning_rate=learning_rate,
                          train_brier=train_brier,train_common_brier=train_common_brier,validation_native_brier=native_brier,
                          validation_common_brier=common_brier,training_regularized_dropout_loss=loss_value,
                          optimization_weighted_prevalence=optimization_prevalence,population_weighted_prevalence=prevalence,
                          optimization_train_brier=optimization_train_brier,
                          gradient_norm=float(gradient_norm.cpu()),parameter_norm=math.sqrt(sum(float(p.detach().square().sum().cpu()) for p in model.parameters())),
                          selected=improved,elapsed_seconds=time.perf_counter()-started)
            if isinstance(model, NeuralMixedNonnegativeKernel):
                record["combiner_parameter_norm"] = math.sqrt(sum(float(p.detach().square().sum().cpu()) for p in model.combiner.parameters()))
            elif isinstance(model, MixedNonnegativeKernel):
                record["mixing_weights"] = model.mixing_weights().detach().cpu().tolist()
            history.append(record)
            if epoch%32==0 or epoch==epochs:
                write_json(history_path,history)
                state = dict(model_state_dict=model.state_dict(),optimizer_state_dict=optimizer.state_dict(),epoch=epoch,
                             best_validation_brier=best_score,cpu_rng_state=torch.get_rng_state(),candidate=candidate,device=str(device),
                             categorical_balance=balance_audit,
                             initial_parameter_sha256=initial_parameter_sha256,scheduler=scheduler,next_optimizer_step=epoch+1,
                             best_checkpoint=torch.load(folder/"checkpoint.pt", map_location="cpu", weights_only=True))
                if device.type=="mps":state["mps_rng_state"]=torch.mps.get_rng_state()
                if device.type=="cuda":state["cuda_rng_states"]=torch.cuda.get_rng_state_all()
                torch.save(state,last_path)
                print(f"{candidate['id']} epoch={epoch}/{epochs} train={train_brier:.7f} val_common={common_brier:.7f} best={best_score:.7f}",flush=True)
        selected = torch.load(folder/"checkpoint.pt",map_location=device,weights_only=True)
        model.load_state_dict(selected["model_state_dict"])
        verification["selected_checkpoint"] = MultiscaleSearch.verify_equivalence(model,train_data,mean,std,candidate["family"],device)
        reloaded = MultiscaleSearch.load_trained_model(folder/"checkpoint.pt",device)
        if not all(torch.equal(a,b) for a,b in zip(model.state_dict().values(),reloaded.model.state_dict().values())):
            raise AssertionError("Checkpoint parameters changed on public reload")
        summary = dict(candidate=candidate,epochs_completed=len(history),best_epoch=selected["best_epoch"],
                       validation_common_brier=best_score,checkpoint=str((folder/"checkpoint.pt").resolve()),
                       train_sample_count=len(train_data),validation_native_sample_count=len(validation_data),
                       validation_common_sample_count=len(validation_tensors.common),early_stopped=False,
                       checkpoint_sha256=MultiscaleSearch.sha256(folder/"checkpoint.pt"),
                       trainable_parameters=sum(p.numel() for p in model.parameters()),verification=verification,
                       test_used_for_selection=False,device=str(device),initial_parameter_sha256=initial_parameter_sha256,
                       categorical_balance=balance_audit,population_weighted_prevalence=prevalence,
                       optimization_weighted_prevalence=optimization_prevalence,
                       final_learning_rate=history[-1]["learning_rate"],scheduling_horizon=scheduler["horizon"])
        if isinstance(model, NeuralMixedNonnegativeKernel):
            summary["combiner_readout"] = "lambda=sum(branch_rates)*softplus(MLP(branch_rates)); scalar nonnegative output, zero at all-zero rates"
            summary["combiner_parameters"] = sum(p.numel() for p in model.combiner.parameters())
        elif isinstance(model, MixedNonnegativeKernel):
            summary["selected_mixing_weights"] = dict(zip(map(str,model.kernel_sizes),model.mixing_weights().detach().cpu().tolist(),strict=True))
            summary["mixing_interpretation"] = "Predictive coefficients; branch scale and mixing amplitude are not separately identifiable"
        write_json(folder/"summary.json",summary)
        return summary


    @staticmethod
    def _run_identity(args):
        """Identify an experiment without using its destination or execution stage."""
        if args.epochs < 1 or args.finalist_epochs < args.epochs:
            raise ValueError("Candidate epochs must be positive and fit inside the finalist horizon")
        candidates = MultiscaleSearch.candidate_plan(args.learning_rates, args.schedules, args.finalist_epochs,
                                    args.warmup_epochs, args.minimum_lr_factor, args.restart_period)
        balance = validate_categorical_balance_settings(**balance_settings_from_args(args))
        metadata = json.loads((args.cache / "metadata.json").read_text())
        sampled_cache = bool(metadata.get("smoke_verification_only", False))
        bound_smoke_cache = sampled_cache and all(key in metadata for key in (
            "smoke_original_cache", "smoke_original_cache_sha256", "smoke_sampling"))
        smoke_mode = sampled_cache or getattr(args, "stage", None) == "smoke"
        cache_path = str(args.cache.resolve())
        cache_hashes = {name: MultiscaleSearch.sha256(args.cache / name) for name in MultiscaleSearch.CACHE_FILES}
        sampling_seed = args.seed
        if bound_smoke_cache:
            # Individual stages can continue a sampled run using its frozen source
            # identity. verify_protocol still verifies all sampled-cache bytes.
            cache_path = metadata["smoke_original_cache"]
            cache_hashes = metadata["smoke_original_cache_sha256"]
            sampling_seeds = {record["seed"] for record in metadata["smoke_sampling"].values()}
            if len(sampling_seeds) != 1:
                raise ValueError("Smoke cache sampling seeds are inconsistent")
            sampling_seed = sampling_seeds.pop()
        return dict(
            cache=cache_path, candidate_epochs=args.epochs,
            finalist_epochs=args.finalist_epochs, seed=args.seed, forest_trees=args.forest_trees,
            learning_rates=[float(v) for v in args.learning_rates], schedules=list(args.schedules),
            scheduling_horizon=args.finalist_epochs, warmup_epochs=args.warmup_epochs,
            minimum_lr_factor=float(args.minimum_lr_factor), restart_period=args.restart_period,
            categorical_balance_settings=balance, candidates=candidates,
            cache_sha256=cache_hashes,
            training_source_sha256={name: MultiscaleSearch.sha256(Path(__file__).parent / name) for name in MultiscaleSearch.TRAINING_SOURCE_FILES},
            training_device=str(choose_device(args.device)),
            mode="smoke" if smoke_mode else "full",
            smoke_sampling=dict(version=1, seed=sampling_seed, train_rows=512, validation_rows=256, test_rows=256)
                if smoke_mode else None,
        )


    @staticmethod
    def _output_conflict(output, identity):
        """Return a configuration conflict; malformed/unbound artifacts are errors."""
        path = output / "protocol.json"
        if not path.exists():
            if output.exists() and any(output.iterdir()):
                raise ValueError(f"Output contains artifacts without protocol.json: {output}; use --run-policy new")
            return None
        protocol = json.loads(path.read_text())
        # New CLI runs bind even the device and original smoke-cache sampling request.
        stored_identity = protocol.get("run_identity")
        if stored_identity is not None:
            if not isinstance(stored_identity, dict) or stored_identity.keys() != identity.keys():
                raise ValueError(f"Invalid run_identity in {path}")
            changed = [key for key, value in identity.items() if stored_identity.get(key) != value]
            if changed:
                return ", ".join(changed)
            MultiscaleSearch.verify_protocol(protocol, Path(protocol["cache"]))
            return None
        # Preserve strict compatibility with experiments created before CLI routing.
        if identity["mode"] == "smoke":
            return "legacy smoke run lacks an original-cache sampling identity"
        for key, value in identity.items():
            if key in ("training_device", "mode", "smoke_sampling"):
                continue
            if key not in protocol:
                raise ValueError(f"Invalid experiment protocol: missing {key} in {path}")
            if protocol[key] != value:
                return key
        device = protocol.get("training_device")
        if device is None and (output / "candidates").exists():
            # Older optimizer states bind their device per candidate, not in protocol.
            summaries = sorted((output / "candidates").glob("*/summary.json"))
            if summaries:
                device = json.loads(summaries[0].read_text())["device"]
            elif any((output / "candidates").iterdir()):
                return "legacy partial run does not record its device in the protocol"
        if device is not None and device != identity["training_device"]:
            return "training_device"
        MultiscaleSearch.verify_protocol(protocol, Path(identity["cache"]))
        return None


    @staticmethod
    def resolve_output(args):
        """Choose once: resume a matching experiment or preserve it and start another."""
        if getattr(args, "_output_resolved", False):
            return args.output
        identity = MultiscaleSearch._run_identity(args)
        requested = args.output
        policy = getattr(args, "run_policy", "auto")
        if policy == "new":
            selected = requested.with_name(f"{requested.name}__new_{time.time_ns()}")
            while selected.exists():
                selected = requested.with_name(f"{requested.name}__new_{time.time_ns()}")
            reason = "fresh run requested"
        else:
            if policy == "resume" and not (requested / "protocol.json").is_file():
                raise ValueError(f"No experiment to resume in {requested}")
            reason = MultiscaleSearch._output_conflict(requested, identity)
            selected = requested
            if reason:
                if policy == "resume":
                    raise ValueError(f"Resume protocol mismatch: {reason}; use --run-policy auto or new")
                digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"),
                                                   allow_nan=False).encode()).hexdigest()[:12]
                selected = requested.with_name(f"{requested.name}__config_{digest}")
                conflict = MultiscaleSearch._output_conflict(selected, identity)
                if conflict:
                    raise ValueError(f"Configuration directory conflict in {selected}: {conflict}; use --run-policy new")
        args.output = selected
        args._run_identity = identity
        args._output_resolved = True
        if selected != requested:
            print(f"Independent benchmark run ({reason}). Existing results preserved.", flush=True)
        print(f"Benchmark output: {selected.resolve()}", flush=True)
        return selected


    @staticmethod
    def setup_from_args(args):
        MultiscaleSearch.resolve_output(args)
        existing = (args.output / "protocol.json").exists()
        protocol = MultiscaleSearch.setup(args.output,args.cache,args.epochs,args.finalist_epochs,args.seed,args.forest_trees,
                         learning_rates=args.learning_rates,schedules=args.schedules,warmup_epochs=args.warmup_epochs,
                         minimum_lr_factor=args.minimum_lr_factor,restart_period=args.restart_period,
                         balance_settings=balance_settings_from_args(args))
        if not existing:
            protocol.update(run_identity=args._run_identity, training_device=args._run_identity["training_device"])
            write_json(args.output / "protocol.json", protocol)
        return protocol


    @staticmethod
    def train_search(args):
        protocol = MultiscaleSearch.setup_from_args(args)
        metadata = json.loads((args.cache/"metadata.json").read_text())
        train_base, validation_base = (MultiscaleSearch.load_split(args.cache,name,metadata) for name in ("train","validation"))
        validate_partition_disjointness({"train": train_base, "validation": validation_base}, metadata)
        device = choose_device(args.device)
        torch.set_num_threads(args.threads)
        summaries = []
        balance_by_k = {}
        for k in MultiscaleSearch.SIZES:
            ti,vi = native_indices(train_base,k),native_indices(validation_base,k)
            train_data, val_data = crop_split(train_base,k,ti),crop_split(validation_base,k,vi)
            balance_by_k[k] = MultiscaleSearch.fit_native_balance(train_data, metadata, protocol, args.output)
            effective, balance_audit = balance_by_k[k]
            mean,std = fit_normalization(train_data, metadata=metadata)
            global_baseline = fit_global_rate(train_data)
            tci = np.flatnonzero(np.isin(ti,common_indices(train_base)))
            ci = np.flatnonzero(np.isin(vi,common_indices(validation_base)))
            for spatial in (False,True):
                family = "legacy" if spatial else "mlp"
                tensors, vt = MultiscaleSearch.tensor_data(train_data,mean,std,family,device,tci,optimization_weight=effective,categorical_balance=balance_audit),MultiscaleSearch.tensor_data(val_data,mean,std,family,device,ci)
                for candidate in [c for c in protocol["candidates"] if c["kernel_size"]==k and ((c["family"] in MultiscaleSearch.SPATIAL_FAMILIES)==spatial)]:
                    summary_path=args.output/"candidates"/candidate["id"]/"summary.json"
                    if summary_path.exists() and json.loads(summary_path.read_text())["epochs_completed"]>=args.epochs:
                        existing = json.loads(summary_path.read_text())
                        if existing["candidate"] != candidate or existing["device"] != str(device):
                            raise ValueError("Resume requires the same candidate configuration and training device")
                        if existing.get("categorical_balance") != balance_audit:
                            raise ValueError("Resume categorical balancing differs from the native training cohort")
                        summaries.append(existing)
                    else:
                        summaries.append(MultiscaleSearch.fit_candidate(candidate,train_data,val_data,tensors,vt,mean,std,global_baseline,metadata,protocol,args.output,device,args.epochs))
                    write_json(args.output/"candidate_selection.json",summaries)
                del tensors,vt
                if device.type=="mps":torch.mps.empty_cache()
            del train_data,val_data
        frozen_finalists=args.output/"finalist_selection.json"
        if frozen_finalists.exists():
            before_extension=json.loads(frozen_finalists.read_text())["selection_before_extension"]
            candidates_by_id={s["candidate"]["id"]:s for s in summaries}
            finalists=[candidates_by_id[s["candidate"]["id"]] for s in before_extension]
        else:
            finalists = [min((s for s in summaries if s["candidate"]["family"]==family),key=lambda s:s["validation_common_brier"]) for family in MultiscaleSearch.NEURAL_FAMILIES]
            write_json(frozen_finalists,dict(selection_before_extension=finalists,test_used_for_selection=False))
        for selected in finalists:
            c=selected["candidate"];k=c["kernel_size"]
            ti,vi=native_indices(train_base,k),native_indices(validation_base,k)
            td,vd=crop_split(train_base,k,ti),crop_split(validation_base,k,vi)
            effective, balance_audit = balance_by_k[k]
            mean,std=fit_normalization(td, metadata=metadata);baseline=fit_global_rate(td)
            ci=np.flatnonzero(np.isin(vi,common_indices(validation_base)))
            tci=np.flatnonzero(np.isin(ti,common_indices(train_base)))
            tensors,vt=MultiscaleSearch.tensor_data(td,mean,std,c["family"],device,tci,optimization_weight=effective,categorical_balance=balance_audit),MultiscaleSearch.tensor_data(vd,mean,std,c["family"],device,ci)
            extended=MultiscaleSearch.fit_candidate(c,td,vd,tensors,vt,mean,std,baseline,metadata,protocol,args.output,device,args.finalist_epochs)
            summaries=[extended if s["candidate"]["id"]==c["id"] else s for s in summaries]
            write_json(args.output/"candidate_selection.json",summaries)
            del tensors,vt,td,vd
            if device.type=="mps":torch.mps.empty_cache()
        write_json(args.output/"neural_complete.json",dict(completed=True,candidates=len(summaries),long_finalists=len(finalists),test_used_for_selection=False))
        MultiscaleSearch.write_learning_rate_comparisons(args.output, protocol, summaries)


    @staticmethod
    def write_learning_rate_comparisons(output, protocol, summaries):
        """Compare rates/schedules at the same first-stage budget and seeded start.

        A continued finalist's later validation outcomes are excluded from this
        comparison so they cannot acquire an unequal 4,096-versus-512 advantage.
        Final model selection can still use the entire authorized trajectory.
        """
        rows = []
        initial_hashes = {}
        for summary in summaries:
            candidate = summary["candidate"]
            base = candidate["base_configuration_id"]
            hashes = initial_hashes.setdefault(base, set())
            hashes.add(summary["initial_parameter_sha256"])
            if len(hashes) != 1:
                raise AssertionError(f"Rate/schedule variants have different initial parameters: {base}")
            history = json.loads((output/"candidates"/candidate["id"]/"history.json").read_text())
            first = history[:protocol["candidate_epochs"]]
            if len(first) != protocol["candidate_epochs"]:
                raise ValueError(f"Incomplete first-stage history: {candidate['id']}")
            best = min(first, key=lambda r: r["validation_common_brier"])
            rows.append(dict(base_configuration_id=base,candidate_id=candidate["id"],family=candidate["family"],
                             kernel_size=candidate["kernel_size"],hidden_channels=candidate["hidden_channels"],
                             depth=candidate["depth"],dropout=candidate["dropout"],weight_decay=candidate["weight_decay"],
                             peak_learning_rate=candidate["learning_rate"],schedule=candidate["scheduler"]["name"],
                             compared_epochs=len(first),best_epoch=best["epoch"],
                             validation_common_brier=best["validation_common_brier"],
                             final_validation_common_brier=first[-1]["validation_common_brier"],
                             final_train_common_brier=first[-1]["train_common_brier"],
                             final_learning_rate=first[-1]["learning_rate"],
                             initial_parameter_sha256=summary["initial_parameter_sha256"],test_used_for_selection=False))
        write_json(output/"learning_rate_comparison.json",dict(compared_epochs=protocol["candidate_epochs"],
                   interpretation="Validation-only matched first-stage budgets and identical initialization within each architecture/kernel/regularization setting; nominal AdamW decay is fixed but integrated shrinkage changes with rate trajectory",
                   test_used_for_selection=False,rows=rows))
        with (output/"learning_rate_comparison.csv").open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        return rows


    @staticmethod
    def forest_search(args):
        protocol=MultiscaleSearch.setup_from_args(args)
        metadata=json.loads((args.cache/"metadata.json").read_text())
        train_base,val_base=(MultiscaleSearch.load_split(args.cache,n,metadata) for n in ("train","validation"))
        validate_partition_disjointness({"train": train_base, "validation": val_base}, metadata)
        selection=[]
        for k in (3,5):
            ti=native_indices(train_base,k)
            td=crop_split(train_base,k,ti)
            effective, balance_audit = MultiscaleSearch.fit_native_balance(td, metadata, protocol, args.output)
            mean,std=fit_normalization(td, metadata=metadata)
            env=(td.environment-mean[None,:,None,None])/std[None,:,None,None]
            ci=common_indices(val_base)
            vd=crop_split(val_base,k,ci)
            ve=(vd.environment-mean[None,:,None,None])/std[None,:,None,None]
            best=None
            for depth in (8,15,None):
                name=f"rf{k}_depth{depth}"
                path=args.output/"forests"/f"{name}.joblib"
                path.parent.mkdir(parents=True,exist_ok=True)
                summary_path=path.with_suffix(".json")
                if summary_path.exists():
                    summary=json.loads(summary_path.read_text())
                    if summary.get("categorical_balance") != balance_audit:
                        raise ValueError("Saved forest summary categorical balancing differs from the native training cohort")
                else:
                    if path.exists():
                        # A completed forest save interrupted before its summary
                        # can be safely recovered without fitting or overwriting it.
                        model=PatchRandomForest.load(path)
                        if model.metadata.get("categorical_balance") != balance_audit:
                            raise ValueError("Saved forest categorical balancing differs from the native training cohort")
                    else:
                        model=PatchRandomForest(k,n_estimators=args.forest_trees,max_depth=depth,random_state=args.seed,n_jobs=args.threads)
                    start=time.perf_counter()
                    if not path.exists():model.fit(env,td.burned,td.target,effective,channel_names=metadata["channels"])
                    p=model.predict_probability(ve,vd.burned,channel_names=metadata["channels"])
                    score=brier(vd.target,p,vd.weight)
                    if not path.exists():model.save(path,metadata=dict(normalization_mean=mean.tolist(),normalization_std=std.tolist(),cache_metadata_sha256=protocol["cache_sha256"]["metadata.json"],categorical_balance=balance_audit,
                                                                        categorical_balance_settings=protocol["categorical_balance_settings"]))
                    reload=PatchRandomForest.load(path)
                    np.testing.assert_allclose(p,reload.predict_probability(ve,vd.burned,channel_names=metadata["channels"]),rtol=0,atol=1e-12)
                    summary=dict(id=name,family="random_forest",kernel_size=k,max_depth=depth,n_estimators=args.forest_trees,
                                 checkpoint=str(path.resolve()),validation_common_brier=score,train_sample_count=len(td),
                                 checkpoint_sha256=MultiscaleSearch.sha256(path),
                                 fit_seconds=time.perf_counter()-start,test_used_for_selection=False,categorical_balance=balance_audit)
                    write_json(summary_path,summary)
                    print(f"{name} val_common={score:.7f} seconds={summary['fit_seconds']:.1f}",flush=True)
                selection.append(summary)
                if best is None or summary["validation_common_brier"]<best["validation_common_brier"]:best=summary
            del env,ve,td,vd
        write_json(args.output/"forest_selection.json",selection)
        write_json(args.output/"forests_complete.json",dict(completed=True,candidates=len(selection),test_used_for_selection=False))


    @staticmethod
    def thresholds(data,p,indices):
        return {name:select_classification_threshold(data.target[indices],p[indices],data.weight[indices],criterion=name) for name in ("f1","mcc")}


    @staticmethod
    def finalize(args):
        MultiscaleSearch.resolve_output(args)
        if not all((args.output/name).exists() for name in ("neural_complete.json","forests_complete.json")):
            raise ValueError("Neural and forest searches must finish before test evaluation")
        protocol=MultiscaleSearch.setup_from_args(args)
        MultiscaleSearch.verify_protocol(protocol,args.cache)
        metadata=json.loads((args.cache/"metadata.json").read_text())
        summaries=json.loads((args.output/"candidate_selection.json").read_text())
        forests=json.loads((args.output/"forest_selection.json").read_text())
        MultiscaleSearch.verify_balance_reports(args.output, protocol, summaries + forests)
        selected=[]
        for family in ("constant","linear",*MultiscaleSearch.NEURAL_FAMILIES):
            for k in ((max(MultiscaleSearch.MIXED_SIZES),) if family in ("mixed", "neural_mixed") else MultiscaleSearch.SIZES):
                selected.append(min((s for s in summaries if s["candidate"]["family"]==family and s["candidate"]["kernel_size"]==k),key=lambda s:s["validation_common_brier"]))
        for k in (3,5):selected.append(min((s for s in forests if s["kernel_size"]==k),key=lambda s:s["validation_common_brier"]))
        best=min(selected,key=lambda s:s["validation_common_brier"])
        for record in selected:
            if record.get("checkpoint_sha256") != MultiscaleSearch.sha256(record["checkpoint"]):
                raise ValueError(f"Selected checkpoint integrity mismatch: {record['checkpoint']}")
            MultiscaleSearch.verify_checkpoint_balance(record)
        write_json(args.output/"selection.json",dict(selected=selected,best=best,test_used_for_selection=False))
        write_json(args.output/"best_models.json",{name:record for record in selected for name in [
            f"{record['candidate']['family']}_k{record['candidate']['kernel_size']}" if "candidate" in record
            else f"random_forest_k{record['kernel_size']}"]})
        # This is the first stage loading test inputs/outcomes.
        metrics={};calibration_thresholds={};identities={}
        for split in ("validation","test","train"):
            data=MultiscaleSearch.load_split(args.cache,split,metadata)
            identities[split] = cell_hour_identities(data)
            common=common_indices(data)
            payload=cohort_payload(data,common)
            native_cohorts={k:native_indices(data,k) for k in MultiscaleSearch.SIZES}
            rows={}
            for record in selected:
                if "candidate" in record:
                    c=record["candidate"];name=c["id"];k=c["kernel_size"]
                    fitted=MultiscaleSearch.load_trained_model(record["checkpoint"],args.device)
                    cropped=crop_split(data,k)
                    mean=fitted.mean[:,0,0].cpu().numpy();std=fitted.std[:,0,0].cpu().numpy()
                    tensors=MultiscaleSearch.tensor_data(cropped,mean,std,c["family"],choose_device(args.device))
                    p=MultiscaleSearch.probabilities(fitted.model,tensors)
                    no_contact=cropped.neighbor_count==0
                    if not np.all(p[no_contact]==0):raise AssertionError("Kernel no-contact probabilities must be structural zeros")
                    coverage=dict(predicted_count=len(p),no_contact_count=int(no_contact.sum()),no_contact_probability_max=float(p[no_contact].max()) if no_contact.any() else None)
                    del tensors,fitted
                else:
                    name=record["id"];k=record["kernel_size"]
                    fitted=PatchRandomForest.load(resolve_recorded_path(record["checkpoint"]))
                    preprocessing=fitted.metadata
                    mean=np.array(preprocessing["normalization_mean"],dtype=np.float32);std=np.array(preprocessing["normalization_std"],dtype=np.float32)
                    cropped=crop_split(data,k)
                    p=np.empty(len(data),dtype=np.float64)
                    for start in range(0,len(data),8192):
                        end=min(start+8192,len(data));e=(cropped.environment[start:end]-mean[None,:,None,None])/std[None,:,None,None]
                        p[start:end]=fitted.predict_probability(e,cropped.burned[start:end],channel_names=metadata["channels"])
                    coverage=dict(predicted_count=len(p),no_contact_count=int((cropped.neighbor_count==0).sum()),no_contact_probability_max=float(p[cropped.neighbor_count==0].max()) if (cropped.neighbor_count==0).any() else None)
                ni=native_cohorts[k]
                if split=="validation":
                    reproduced=brier(data.target[common],p[common],data.weight[common])
                    if not math.isclose(reproduced,record["validation_common_brier"],rel_tol=0,abs_tol=2e-6):
                        raise AssertionError(f"Selected checkpoint validation score mismatch: {name}")
                    calibration_thresholds[name]={"common":MultiscaleSearch.thresholds(data,p,common),"native":MultiscaleSearch.thresholds(data,p,ni)}
                t=calibration_thresholds[name]
                rows[name]=dict(kernel_size=k,coverage=coverage,
                                native=probability_metrics_with_all(data.target[ni],p[ni],data.weight[ni],cropped.neighbor_count[ni],thresholds=t["native"]),
                                common=probability_metrics_with_all(data.target[common],p[common],data.weight[common],cropped.neighbor_count[common],thresholds=t["common"]))
                rows[name]["categorical_groups"] = {
                    "native": categorical_group_metrics(cropped, p, metadata, indices=ni),
                    "common": categorical_group_metrics(cropped, p, metadata, indices=common),
                }
                rows[name]["native"]["calibration"]=weighted_calibration(data.target[ni],p[ni],data.weight[ni])
                rows[name]["common"]["calibration"]=weighted_calibration(data.target[common],p[common],data.weight[common])
                payload[name]=p[common]
                dest=args.output/"predictions"/split;dest.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(dest/f"{name}.npz",p=p,source_index=np.arange(len(data)),native_index=ni,common_index=common)
            dest=args.output/"predictions";dest.mkdir(exist_ok=True)
            np.savez_compressed(dest/f"{split}_common.npz",**payload)
            metrics[split]=dict(common_cohort=cohort_summary(data,common,3),native_cohorts={str(k):cohort_summary(data,native_cohorts[k],k) for k in MultiscaleSearch.SIZES},models=rows)
            write_json(args.output/"metrics.json",metrics)
            del data
        write_json(args.output/"classification_thresholds.json",calibration_thresholds)
        partition_verification = validate_partition_disjointness(identities, metadata)
        write_json(args.output/"partition_verification.json", partition_verification)
        MultiscaleSearch.report(args.output,protocol,selected,best,metrics)
        MultiscaleSearch.verify_protocol(protocol,args.cache)
        write_json(args.output/"complete.json",dict(completed=True,neural_candidates=len(summaries),forest_candidates=len(forests),evaluated_models=len(selected),
                                                  test_used_for_selection=False,cache_sha256_verified={n:MultiscaleSearch.sha256(args.cache/n)==v for n,v in protocol["cache_sha256"].items()}))


    @staticmethod
    def report(output,protocol,selected,best,metrics):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        def label(s):
            c=s.get("candidate",s)
            if c.get("family") in ("mixed", "neural_mixed"):
                return ("neural mixed (" if c["family"]=="neural_mixed" else "linear mixed (") + ", ".join(f"{k}x{k}" for k in c["kernel_sizes"]) + ")"
            return f"{c.get('family')} {c['kernel_size']}x{c['kernel_size']}"
        def name(s):return s.get("candidate",s)["id"]
        def fmt(v):return f"{v:.6f}" if isinstance(v,(float,int)) else str(v)
        partition_description = MultiscaleSearch.split_description(protocol)
        rate_text = ", ".join(f"{value:g}" for value in protocol["learning_rates"])
        schedule_text = ", ".join(protocol["schedules"])
        lines=["# Fresh single-scale, linear mixed and neural mixed scheduling search", "",f"Validation selected **{label(best)}** among the searched configurations. All test scores below were computed after selection.","",
               partition_description,"",MultiscaleSearch.balance_description(protocol),"",
               "The target is a currently unburned cell becoming burned at exactly the next hourly snapshot. Contact uses the reconstructed current cumulative burned-area map; it does not mean an actively flaming cell.","",
               f"Every candidate completed {protocol['candidate_epochs']} full-batch epochs. One validation-selected candidate in each of six neural families continued, with optimizer and RNG state, to {protocol['finalist_epochs']} epochs. There was no early stopping. A saved prediction checkpoint can occur before the final epoch because selection minimizes validation Brier over the entire trajectory.","",
               "All fits are fresh. Constant kernels learn offset-specific rates; linear kernels map per-channel environmental patch means to nonnegative rates; MLP and residual MLP families use the same patch means; the existing CNN and new regularized CNN preserve full spatial environmental patches. Every kernel fixes its center to zero and computes q=1-exp(-sum(nonnegative offset rate × current burned neighbor)). Random forests are separate probability-classifier baselines, not learned rate kernels.","",
               "Training uses native K-contact rows from one frozen 9x9 sample cache and its original inverse inclusion weights. Native evaluation also uses K-contact. The matched comparison uses the exact same current 3x3-contact rows for every model, retaining the original weights. No-contact predictions are saved for every model; neural kernels return a valid structural zero, and forests may return nonzero probabilities.","",
               f"Optimization is AdamW with full-batch categorical optimization-weighted Brier divided by optimization-weighted training prevalence, weight decay, optional dropout, and gradient norm clipping at 10. An epoch is one pass over every native training row and ONE optimizer step, with chunked gradient accumulation. The ten single-scale architecture/regularization settings at four kernel sizes and three linear mixed plus three neural mixed CNN settings (branch widths 16, 32, 64) are each crossed with peak learning rates **{rate_text}** and schedules **{schedule_text}**, giving {len(protocol['candidates'])} kernel candidates. Width, depth, dropout, and weight decay retain the prior joint search settings. The learning-rate/schedule subgrid is fully crossed; the architecture search remains finite and joint.","",
               f"The fixed scheduling horizon is **{protocol['scheduling_horizon']} optimizer steps from the start of every candidate**, even when its initial fit stops after {protocol['candidate_epochs']} steps. Continuing a finalist restores its AdamW and RNG states and resumes the original schedule. It does not start warmup again or rebase the cosine schedule. Warmup lasts {protocol['warmup_epochs']} steps; the rate floor is {protocol['minimum_lr_factor']:g} times the peak; optional restart cycles last {protocol['restart_period']} steps. The rate actually used is saved at every epoch as `learning_rate`, with a one-based `optimizer_step`.","",
               "Constant schedules always use the peak. Linear warmup uses peak × step / warmup_length. For a nonzero warmup, ordinary cosine uses floor + (peak − floor) × (1 + cos(π × (step − warmup_length)/(horizon − warmup_length)))/2 after warmup and reaches the floor at the fixed horizon. Without warmup its cosine progress is (step − 1)/(horizon − 1). Restart schedules use cycles with progress 0/(period − 1), …, (period − 1)/(period − 1) after warmup, then restart at the peak. Scheduling never consults validation or test scores.","",
               "Every variant of the same kernel/architecture/regularization setting shares its initial parameter checksum and random seed. AdamW's nominal weight-decay coefficient stays fixed within each comparison, but its per-step shrinkage multiplier is 1 − learning_rate × weight_decay, so changing rates or schedules also changes integrated parameter shrinkage. The controlled comparison below therefore measures the complete optimizer policy at fixed nominal regularization. It does not isolate learning rate from accumulated weight decay.","",
               "## Matched test comparison", "", "| Model | Completed / selected epoch | Validation Brier | Test Brier | AP | ROC AUC | Exact NLL | F1 at validation threshold | MCC at validation threshold |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        csv_rows=[]
        for s in sorted(selected,key=lambda s:s["validation_common_brier"]):
            n=name(s);m=metrics["test"]["models"][n]["common"]
            epoch=f"{s['epochs_completed']} / {s['best_epoch']}" if "epochs_completed" in s else "trees"
            policy = f"; peak={s['candidate']['learning_rate']:g}, {s['candidate']['scheduler']['name']}" if "candidate" in s else ""
            lines.append(f"| {label(s)}{policy} | {epoch} | {fmt(s['validation_common_brier'])} | {fmt(m['brier'])} | {fmt(m['average_precision'])} | {fmt(m['roc_auc'])} | {fmt(m['exact_negative_log_likelihood_mean'])} | {fmt(m['f1_at_validation_f1_threshold'])} | {fmt(m['mcc_at_validation_mcc_threshold'])} |")
            csv_rows.append(dict(model=n,label=label(s),validation_brier=s["validation_common_brier"],**{key:value for key,value in m.items() if not isinstance(value,(list,dict))}))
        lines += ["", "## Cohort sizes", "", "| Split | Full prediction rows | 3x3 contact | 5x5 contact | 7x7 contact | 9x9 contact | Matched positives |", "|---|---:|---:|---:|---:|---:|---:|"]
        for split in ("train","validation","test"):
            c=metrics[split];lines.append(f"| {split} | {c['common_cohort']['base_sample_count']} | " + " | ".join(str(c["native_cohorts"][str(k)]["sample_count"]) for k in MultiscaleSearch.SIZES)+f" | {c['common_cohort']['positive_sample_count']} |")
        lines += ["", "## Native test comparison", "", "These scores use different K-contact populations and therefore cannot rank kernel sizes fairly. Compare model families within the same K, or use the matched table above.","", "| Model | Native test Brier | Native AP | Native ROC AUC |", "|---|---:|---:|---:|"]
        for s in selected:
            m=metrics["test"]["models"][name(s)]["native"]
            lines.append(f"| {label(s)} | {fmt(m['brier'])} | {fmt(m['average_precision'])} | {fmt(m['roc_auc'])} |")
        comparisons=json.loads((output/"learning_rate_comparison.json").read_text())["rows"]
        lines += ["", "## Controlled learning-rate and schedule comparison", "",
                  f"Each row below fixes kernel size, architecture, dropout, weight decay, training rows, normalization, initialization, and seed. Every entry is its minimum matched validation Brier through the same first {protocol['candidate_epochs']} steps. Later finalist outcomes are excluded from this table. Full candidate trajectories and end-of-budget values are in `learning_rate_comparison.csv` and `history.json`.","",
                  "| Fixed base configuration | " + " | ".join(f"{rate:g} {schedule}" for rate in protocol["learning_rates"] for schedule in protocol["schedules"]) + " |",
                  "|---|" + "---:|"*(len(protocol["learning_rates"])*len(protocol["schedules"]))]
        for base in dict.fromkeys(row["base_configuration_id"] for row in comparisons):
            variant={(row["peak_learning_rate"],row["schedule"]):row for row in comparisons if row["base_configuration_id"]==base}
            lines.append(f"| {base} | " + " | ".join(fmt(variant[(rate,schedule)]["validation_common_brier"]) for rate in protocol["learning_rates"] for schedule in protocol["schedules"]) + " |")
        summaries=json.loads((output/"candidate_selection.json").read_text())
        by_id={name(row):row for row in summaries}
        finalists=json.loads((output/"finalist_selection.json").read_text())["selection_before_extension"]
        finalists=[by_id[name(row)] for row in finalists]
        plot_rows=math.ceil(len(MultiscaleSearch.NEURAL_FAMILIES)/2)
        fig,axes=plt.subplots(plot_rows,2,figsize=(13,4.5*plot_rows),constrained_layout=True,squeeze=False)
        lr_fig,lr_axes=plt.subplots(plot_rows,2,figsize=(13,4.5*plot_rows),constrained_layout=True,squeeze=False)
        diagnostics={}
        for ax,lr_ax,family in zip(axes.flat,lr_axes.flat,MultiscaleSearch.NEURAL_FAMILIES):
            s=next(row for row in finalists if row["candidate"]["family"]==family)
            h=json.loads((output/"candidates"/name(s)/"history.json").read_text())
            x=np.array([r["epoch"] for r in h]);v=np.array([r["validation_common_brier"] for r in h]);tr=np.array([r["train_common_brier"] for r in h])
            ax.plot(x,tr,label="matched training Brier");ax.plot(x,v,label="matched validation Brier")
            ax.axvline(protocol["candidate_epochs"],color="gray",linestyle=":",label="end of initial search")
            ax.scatter([s["best_epoch"]],[s["validation_common_brier"]],color="red",s=25,zorder=4,label="selected checkpoint")
            ax.set(xscale="log",xlabel="Epoch (log scale)",ylabel="Weighted Brier",title=f"{label(s)}; full {len(h)} epochs")
            ax.legend(fontsize=8)
            actual_lr=np.array([r["learning_rate"] for r in h])
            lr_ax.plot(x,actual_lr,label="actual optimizer learning rate")
            lr_ax.axvline(protocol["candidate_epochs"],color="gray",linestyle=":",label="end of initial search")
            lr_ax.set(xlabel="Optimizer step (= epoch)",ylabel="Learning rate",title=f"{label(s)}; {s['candidate']['scheduler']['name']}; peak={s['candidate']['learning_rate']:g}")
            lr_ax.legend(fontsize=8)
            early=min(v[:protocol["candidate_epochs"]]);late=min(v[protocol["candidate_epochs"]:]) if len(v)>protocol["candidate_epochs"] else None
            diagnostics[family]=dict(candidate=name(s),best_first_stage_validation_brier=float(early),best_late_validation_brier=float(late) if late is not None else None,
                                     relative_late_improvement=(float((early-late)/early) if late is not None else None),
                                     best_epoch=s["best_epoch"],final_training_brier=float(tr[-1]),minimum_training_brier=float(tr.min()),
                                     peak_learning_rate=s["candidate"]["learning_rate"],scheduler=s["candidate"]["scheduler"],
                                     initial_learning_rate=float(actual_lr[0]),final_learning_rate=float(actual_lr[-1]),
                                     interpretation="Descriptive late improvement only. " + partition_description + " No verified interpolation threshold or multi-seed grokking claim.")
        for axis in list(axes.flat)[len(MultiscaleSearch.NEURAL_FAMILIES):] + list(lr_axes.flat)[len(MultiscaleSearch.NEURAL_FAMILIES):]:
            axis.set_visible(False)
        mixed = next(record for record in selected if record.get("candidate", {}).get("family") == "mixed")
        mix = mixed["selected_mixing_weights"]
        lines += ["", "## Mixed kernel model", "",
                  "Independent environmental CNN branches generate nonnegative kernels at 3x3, 5x5, 7x7, and 9x9. Each branch's center coefficient is zero. Global learned nonnegative scalar coefficients have unrestricted sum. Their burned-state convolution rates are linearly combined, and one exponential converts that sum into a probability: q_i = 1 - exp(-sum_K alpha_K r_i^(K)). This is not an average of branch probabilities.", "",
                  "Mixed-model training and native evaluation use current contact within the union 9x9 support. Matched evaluation uses the same centered 3x3-contact rows as all single-scale models. Smaller branches crop the central environmental and burned patches; they remain zero when only outer-ring neighbors are burned.", "",
                  "The selected checkpoint mixing coefficients are " + ", ".join(f"alpha_{k}={value:.7g}" for k,value in mix.items()) + ". These are jointly learned predictive coefficients. Rescaling a branch kernel and inversely rescaling its coefficient preserves the combined rate, so these weights alone do not measure uniquely identifiable or causal importance of a spatial scale.", "",
                  "Mixed initialization assigns overlap-adjusted branch offset rates so the initial effective 9x9 kernel has the same uniform per-offset rate as the fitted global baseline. All branches and mixing coefficients are optimized jointly; no separately fitted branch is frozen.", ""]
        h=json.loads((output/"candidates"/name(next(s for s in finalists if s["candidate"]["family"]=="mixed"))/"history.json").read_text())
        mix_fig,mix_ax=plt.subplots(figsize=(9,4),constrained_layout=True)
        for index,k in enumerate(MultiscaleSearch.MIXED_SIZES):
            mix_ax.plot([row["epoch"] for row in h],[row["mixing_weights"][index] for row in h],label=f"{k}x{k}")
        mix_ax.set(xlabel="Optimizer step (= epoch)",ylabel="Learned nonnegative mixing coefficient",title="Mixed finalist: global coefficients (unrestricted sum)")
        mix_ax.legend()
        mix_fig.savefig(output/"mixing_weight_curves.png",dpi=180);plt.close(mix_fig)
        lines += ["![Learned mixing coefficients](mixing_weight_curves.png)", ""]
        neural = next(record for record in selected if record.get("candidate", {}).get("family") == "neural_mixed")
        nc = neural["candidate"]
        lines += ["## Neural mixed kernel model", "",
                  "The additional model feeds the four independent branch convolution rates, ordered 3x3/5x5/7x7/9x9, into a small neural combiner. It produces one nonnegative combined rate before one exponential, rather than four learned mixing weights. The exact scalar readout is lambda_i = (sum_K r_i^(K)) * softplus(MLP(r_i)); q_i = 1 - exp(-lambda_i). Multiplying by the total raw rate ensures exact zero whenever all branch inputs are zero.", "",
                  f"The selected combiner is 4 -> {nc['combiner_hidden_channels']} -> 1, with SiLU and dropout {nc['combiner_dropout']:g}. Branches have hidden width {nc['hidden_channels']}, dropout {nc['dropout']:g}; AdamW weight decay is {nc['weight_decay']:g}. Its complete branch and combiner parameters are saved in the selected checkpoint. The final scalar gain initializes to one so its initial effective rate matches the same uniform global baseline.", "",
                  "The neural combined rate is nonlinear in the current burned map. An environmental kernel alone cannot represent that rate; branch_kernel_rates remain inspectable, while the model's combined rate is obtained through the full prediction or center/combined_rate methods. Native and matched evaluation use the same 9x9 union-contact and centered 3x3-contact conditions as the linear mixed model.", ""]
        fig.savefig(output/"learning_curves.png",dpi=180);plt.close(fig)
        lr_fig.savefig(output/"learning_rate_curves.png",dpi=180);plt.close(lr_fig)
        write_json(output/"learning_diagnostics.json",diagnostics)
        lines += ["", "## Long-training observations", "", "![Learning curves](learning_curves.png)","",
                  "These panels show the six candidates selected for uninterrupted long training. A family/kernel winner in the test table can be a different, shorter candidate when it has a better validation checkpoint.","",
                  "![Actual optimizer learning rates](learning_rate_curves.png)","",
                  "The learning-rate panels plot rates read back from the saved per-step histories. Constant-rate controls remain available for interpreting delayed generalization without a changing learning rate. An improvement during rate decay, or after a restart, is associated with the chosen optimizer policy and alone does not establish grokking.","",
                  f"These curves show training and validation Brier under the same current 3x3-contact condition. {partition_description} Native training Brier is also saved in each history. A decrease after epoch {protocol['candidate_epochs']} is descriptive evidence of late validation improvement. Grokking requires a demonstrated memorization phase followed by delayed generalization; double descent requires a reproducible rise and subsequent fall around an interpolation regime. Neither is inferred automatically from a long run or a visually noisy curve. The references concern particular experimental settings and do not guarantee either phenomenon on reconstructed wildfire labels.","",
                  "[Grokking paper](https://arxiv.org/abs/2201.02177) and [Deep Double Descent paper](https://arxiv.org/abs/1912.02292).", ""]
        for family,d in diagnostics.items():
            lines.append(f"- {family}: best validation Brier through epoch {protocol['candidate_epochs']}={d['best_first_stage_validation_brier']:.6f}; after epoch {protocol['candidate_epochs']}={fmt(d['best_late_validation_brier'])}; selected epoch={d['best_epoch']}; minimum matched training Brier={d['minimum_training_brier']:.6f}.")
        lines += ["", "## Saved artifacts and limits", "", "`protocol.json` binds all input cache hashes, source hashes and the prespecified search. `candidate_selection.json`, `finalist_selection.json` and `selection.json` record validation-only selection. Candidate folders contain the complete per-epoch histories, selected public checkpoints and resumable final optimizer/RNG states. `predictions/` retains probabilities for all base rows and matched identities/weights. `metrics.json` retains calibration, exact and clipped NLL, Bernoulli distances, KL, AP, PR AUC, F1 and MCC. Classification thresholds are selected independently on native and matched validation populations.","",
                  "The training labels are retrospective reconstructions. Scores are inverse-inclusion-weighted sampled estimates, not exact full-grid population scores. No active-flame residence assumption was introduced. The search uses one seed and does not establish robustness, a globally best parameter setting, double descent, or grokking.", ""]
        if protocol.get("smoke_verification_only"):
            lines[2:2] = ["**EXECUTION VERIFICATION ONLY.** This short run uses a small sampled subset of the real cache and reduced epoch/tree budgets. Its numerical scores verify the pipeline and must not be used as scientific model rankings, population estimates, or evidence of grokking/double descent.", ""]
        (output/"report.md").write_text("\n".join(lines))
        fields=sorted(set().union(*(r.keys() for r in csv_rows)))
        with (output/"metrics.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(csv_rows)


    @staticmethod
    def run_all(args):
        MultiscaleSearch.train_search(args)
        MultiscaleSearch.forest_search(args)
        MultiscaleSearch.finalize(args)


    @staticmethod
    def smoke(args):
        """Run every family/stage on real cache subsets with a short epoch budget."""
        source=args.cache
        if args.output==MultiscaleSearch.DEFAULT_OUTPUT:args.output=MultiscaleSearch.DEFAULT_SMOKE_OUTPUT
        args.epochs=2;args.finalist_epochs=4;args.forest_trees=9
        args.warmup_epochs=1;args.restart_period=2
        MultiscaleSearch.resolve_output(args)
        destination=args.output/"smoke_cache"
        if not destination.exists():
            metadata=json.loads((source/"metadata.json").read_text())
            destination.mkdir(parents=True)
            rng=np.random.default_rng(args.seed)
            sampling={}
            for split in ("train","validation","test"):
                data=MultiscaleSearch.load_split(source,split,metadata)
                count=512 if split=="train" else 256
                c3=data.burned[:,:,3:6,3:6].sum((1,2,3))>0
                c9=data.neighbor_count>0
                groups=[c3 & (data.target==label) for label in (0,1)] + [~c9 & (data.target==label) for label in (0,1)]
                indices=[]
                for mask in groups:
                    candidates=np.flatnonzero(mask)
                    indices.extend(rng.choice(candidates,min(32,len(candidates)),replace=False).tolist())
                remaining=np.setdiff1d(np.arange(len(data)),indices)
                indices=np.sort(np.r_[indices,rng.choice(remaining,count-len(indices),replace=False)]).astype(np.int64)
                payload={key:getattr(data,key)[indices] for key in CachedSplit.__dataclass_fields__}
                np.savez_compressed(destination/f"{split}.npz",**payload,original_base_index=indices)
                sampling[split]=dict(base_rows=len(data),smoke_rows=count,seed=args.seed)
            metadata.update(smoke_verification_only=True,smoke_original_cache=str(source.resolve()),smoke_sampling=sampling,
                            smoke_original_cache_sha256=args._run_identity["cache_sha256"])
            write_json(destination/"metadata.json",metadata)
        args.cache=destination
        MultiscaleSearch.run_all(args)


    @staticmethod
    def parser():
        p=argparse.ArgumentParser(description=MultiscaleSearch.__doc__)
        p.add_argument("stage",choices=("run","smoke","train","forests","finalize"))
        p.add_argument("--cache",type=Path,default=MultiscaleSearch.DEFAULT_CACHE)
        p.add_argument("--output",type=Path,default=MultiscaleSearch.DEFAULT_OUTPUT)
        p.add_argument("--run-policy",choices=("auto","resume","new"),default="auto",
                       help="auto resumes matching settings or selects an independent configuration folder; "
                            "resume requires an exact match; new always starts a fresh independent run")
        p.add_argument("--epochs",type=int,default=512)
        p.add_argument("--finalist-epochs",type=int,default=4096)
        p.add_argument("--learning-rates",type=float,nargs="+",default=list(MultiscaleSearch.DEFAULT_LEARNING_RATES),
                       help="Peak rates crossed with every fixed kernel/architecture/regularization configuration")
        p.add_argument("--schedules",choices=SCHEDULES,nargs="+",default=list(MultiscaleSearch.DEFAULT_SCHEDULES),
                       help="constant controls and warmup_cosine by default; optionally add warmup_cosine_restarts")
        p.add_argument("--warmup-epochs",type=int,default=32,help="Linear warmup steps for nonconstant schedules")
        p.add_argument("--minimum-lr-factor",type=float,default=.01,help="Cosine floor as a fraction of the peak learning rate")
        p.add_argument("--restart-period",type=int,default=512,help="Post-warmup optimizer steps per optional cosine restart cycle")
        p.add_argument("--seed",type=int,default=7)
        add_categorical_balance_arguments(p)
        p.add_argument("--threads",type=int,default=4)
        p.add_argument("--forest-trees",type=int,default=100)
        p.add_argument("--device",default="auto",help="auto chooses MPS, then CUDA, then CPU; resume requires same training device")
        return p


    @staticmethod
    def main():
        args=MultiscaleSearch.parser().parse_args()
        if args.device=="auto":args.device="mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        if args.epochs<1 or args.finalist_epochs<args.epochs or args.threads<1:
            raise ValueError("Epochs/threads must be positive and finalist budget must include initial training")
        {"run":MultiscaleSearch.run_all,"smoke":MultiscaleSearch.smoke,"train":MultiscaleSearch.train_search,"forests":MultiscaleSearch.forest_search,"finalize":MultiscaleSearch.finalize}[args.stage](args)


class PortableSearch:
    """Run the multiscale search on a copied checkout using CPU, MPS, or CUDA.

    Defaults locate the original prepared cache and environmental data relative to
    this module, not the original machine's absolute paths. A verified cache clone
    changes only the source-data root. Each root gets its own clone, and default
    experiment directories are separate for every execution device and stage type.
    The frozen training implementation and existing experiment files stay intact.
    """

    __doc__ = __doc__.replace("\n    ", "\n")
    __file__ = __file__
    search = MultiscaleSearch
    choose_device = staticmethod(choose_device)
    relocate_cache = staticmethod(relocate_cache)

    PACKAGE = Path(__file__).resolve().parent
    DEFAULT_DATA_ROOT = DATA_ROOT


    @staticmethod
    def parser():
        result = PortableSearch.search.parser()
        result.description = PortableSearch.__doc__
        # This launcher verifies the historical original-cache bindings. New
        # weighted split caches are passed directly to the multiscale runner.
        result.set_defaults(output=None, cache=DEFAULT_SOURCE_CACHE)
        for action in result._actions:
            if action.dest == "device":
                action.help = "auto selects available CUDA, then MPS, then CPU; resume requires the same training device"
            elif action.dest == "cache":
                action.help = "Original unmodified full 9x9 prepared_all cache; a relocated copy is created automatically"
            elif action.dest == "output":
                action.help = "Experiment directory; defaults to a separate portable directory for the selected device"
        result.add_argument("--data-root", type=Path, default=PortableSearch.DEFAULT_DATA_ROOT,
                            help="Complete original environmental data; defaults to data/environment in this checkout")
        result.add_argument("--portable-cache", type=Path,
                            help="Optional destination for the relocated cache; defaults to a separate directory for this data-root path")
        result.add_argument("--check-only", action="store_true",
                            help="Verify device, relocation, and search setup in a temporary output without training")
        return result


    @staticmethod
    def prepare_args(args):
        """Resolve host paths/device and verify inputs before dispatching training."""
        if args.epochs < 1 or args.finalist_epochs < args.epochs or args.threads < 1:
            raise ValueError("Epochs/threads must be positive and finalist budget must include initial training")
        if args.device == "auto":
            args.device = ("cuda" if torch.cuda.is_available() else
                           "mps" if torch.backends.mps.is_available() else "cpu")
        # Explicit unavailable devices fail before any cache or output is created.
        PortableSearch.choose_device(args.device)
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
            args.output = PortableSearch.search.RUNS / f"20261009_multiscale_{run_name}_{device_label}_categorical_balanced_portable" / cache_id
        else:
            args.output = args.output.resolve()
        print(f"Execution device: {args.device}", flush=True)
        record = PortableSearch.relocate_cache(source, args.portable_cache, args.data_root)
        args.cache = args.portable_cache
        print(f"Cache {record['status']}: {args.cache}", flush=True)
        print(f"Verified original environmental sources: {record['verified_source_files']}", flush=True)
        print(f"Experiment output: {args.output}", flush=True)
        return args


    @staticmethod
    def main():
        args = PortableSearch.prepare_args(PortableSearch.parser().parse_args())
        if args.check_only:
            # A preflight must not bind the requested experiment output or conflict
            # with smoke's reduced epoch budget. Only the verified cache clone is
            # retained; the trial protocol and source snapshot are temporary.
            trial_args = copy.copy(args)
            trial_args.run_policy = "auto"
            with tempfile.TemporaryDirectory(prefix="wildfire-search-preflight-") as directory:
                trial_args.output = Path(directory) / "preflight"
                protocol = PortableSearch.search.setup_from_args(trial_args)
            print(json.dumps(dict(status="passed", device=args.device,
                                  candidate_count=len(protocol["candidates"]),
                                  verified_source_files=protocol["verified_source_files"],
                                  cache=str(args.cache), intended_output=str(args.output),
                                  training_started=False, experiment_output_modified=False), indent=2))
            return
        stages = {"run": PortableSearch.search.run_all, "smoke": PortableSearch.search.smoke, "train": PortableSearch.search.train_search,
                  "forests": PortableSearch.search.forest_search, "finalize": PortableSearch.search.finalize}
        # Keep the frozen source/protocol and training arithmetic intact. Only the
        # cached-versus-public equivalence checks temporarily use full CUDA float32.
        with strict_cuda_equivalence(PortableSearch.search):
            stages[args.stage](args)
        if args.stage in ("run", "smoke", "finalize") and args.output is not None and (args.output / "complete.json").is_file():
            # Reporting is outside the frozen training-source set. Adding figures
            # must not invalidate an existing optimizer checkpoint or its protocol.
            from .report import generate_evaluation_report

            manifest = generate_evaluation_report(args.output)
            print(f"Complete evaluation report: {manifest['metric_count']} metrics, "
                  f"{len(manifest['figures'])} metric graphs, "
                  f"{len(manifest['reliability_figures'])} reliability graphs", flush=True)


def main():
    """Run the original unsigned single-scale search."""
    return Search.main()


def scheduled_main():
    """Run the rate-by-schedule search."""
    return ScheduledSearch.main()


def mixed_main():
    """Run the single-scale and mixed-kernel search."""
    return MixedSearch.main()


def multiscale_main():
    """Run the single-scale, mixed, and neural-mixed search."""
    return MultiscaleSearch.main()


def portable_main():
    """Launch portable search with MPS fallback and one BLAS thread."""
    import os

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    return PortableSearch.main()


def precision_main():
    """Launch a prepared cache with strict CUDA equivalence checks."""
    import os

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    with strict_cuda_equivalence(MultiscaleSearch):
        return MultiscaleSearch.main()


if __name__ == "__main__":
    main()
