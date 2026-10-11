"""Mixed-checkpoint public loading, saved preprocessing, and heat integration."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from wildfire.heat import AffineGrid
from wildfire.heat import CombustionParameters
from wildfire.heat import WildfireHeatModel
from wildfire import WildfireModel
from wildfire import load_model


def _assert_prediction_equal(left, right):
    for name in left.__dataclass_fields__:
        torch.testing.assert_close(getattr(left, name), getattr(right, name),
                                   rtol=0, atol=0, equal_nan=True)


@pytest.fixture
def mixed_checkpoint(tmp_path):
    from wildfire.models import build_mixed_kernel_model
    from wildfire.models import mixed_model_configuration

    torch.manual_seed(193)
    model = build_mixed_kernel_model(
        2, kernel_sizes=(3, 5), branch_architecture="cnn", hidden_channels=4,
        depth=1, dropout=0.0, mixing_constraint="nonnegative",
    )
    contract = {
        "format_version": 1, "architecture": "MixedNonnegativeKernel",
        "in_channels": 2, "channels": ["fixture.a", "fixture.b"],
        "kernel_size": 5, "kernel_model": mixed_model_configuration(model),
        "dt_hours": 1.0, "center_rate": 0.0,
        "eligibility": "at_least_one_burned_neighbor",
    }
    payload = {
        "contract": contract, "model_state_dict": model.state_dict(),
        "normalization_mean": torch.tensor([3.0, 4.0]),
        "normalization_std": torch.tensor([2.0, 5.0]), "best_epoch": 11,
        "validation_brier": 0.03, "configuration": {"seed": 193},
    }
    path = tmp_path / "mixed.pt"
    torch.save(payload, path)
    return path


@pytest.fixture
def mixed_inputs():
    rng = np.random.default_rng(194)
    environment = rng.normal(size=(2, 11, 11)).astype(np.float32)
    burned = np.zeros((1, 11, 11), dtype=np.float32)
    burned[:, 5, 5] = 1.0
    feature_valid = np.ones_like(environment, dtype=bool)
    return burned, environment, feature_valid


def test_mixed_package_and_public_loader_preserve_normalization_and_predictions(mixed_checkpoint, mixed_inputs):
    from wildfire.inference import load_trained_model

    direct = load_trained_model(mixed_checkpoint)
    public = load_model(mixed_checkpoint)
    burned, environment, valid = mixed_inputs
    with torch.inference_mode():
        expected = direct(torch.from_numpy(burned), torch.from_numpy(environment),
                          channel_names=("fixture.a", "fixture.b"),
                          feature_valid=torch.from_numpy(valid))
    result = public.predict_details(burned, environment, channel_names=public.channel_names,
                                    feature_valid=valid)
    _assert_prediction_equal(expected, result)
    assert public.family == "exponential"
    assert public.contract["kernel_model"]["kernel_sizes"] == [3, 5]
    assert public.predictor.best_epoch == 11
    torch.testing.assert_close(public.predictor.mean[:, 0, 0], torch.tensor([3.0, 4.0]))
    torch.testing.assert_close(public.predictor.std[:, 0, 0], torch.tensor([2.0, 5.0]))
    assert public.checkpoint_sha256 == sha256(mixed_checkpoint.read_bytes()).hexdigest()
    assert result.valid[0, 5, 6] and result.probability[0, 5, 6] > 0
    assert not result.valid[0, 0, 0]
    assert torch.isnan(result.probability[0, 0, 0])
    with pytest.raises(ValueError, match="channel names/order"):
        public.predict_details(burned, environment, channel_names=("fixture.b", "fixture.a"))


def test_mixed_public_prediction_accepts_no_contact_and_preserves_unknown_masks(mixed_checkpoint, mixed_inputs):
    public = load_model(mixed_checkpoint)
    _, environment, valid = mixed_inputs
    no_contact = np.zeros((1, 11, 11), dtype=np.float32)
    result = public.predict_details(no_contact, environment, channel_names=public.channel_names,
                                    feature_valid=valid, boundary="zero")
    assert result.valid.all()
    assert result.rate_valid.all()
    assert torch.count_nonzero(result.probability) == 0
    assert torch.count_nonzero(result.rate) == 0
    valid[:, 5, 5] = False
    missing_feature = public.predict_details(no_contact, environment, channel_names=public.channel_names,
                                             feature_valid=valid, boundary="zero")
    assert not missing_feature.valid[0, 5, 5]
    assert torch.isnan(missing_feature.probability[0, 5, 5])
    source_valid = np.ones_like(no_contact, dtype=bool)
    source_valid[:, 5, 5] = False
    missing_source = public.predict_details(no_contact, environment, channel_names=public.channel_names,
                                            burned_area_valid=source_valid, boundary="zero")
    assert not missing_source.valid[0, 5, 6]
    assert torch.isnan(missing_source.probability[0, 5, 6])


def test_mixed_public_save_reloads_resident_state_and_all_configuration(mixed_checkpoint, mixed_inputs, tmp_path):
    public = load_model(mixed_checkpoint)
    burned, environment, valid = mixed_inputs
    with torch.no_grad():
        next(public.predictor.model.parameters()).add_(0.1)
    expected = public.predict_details(burned, environment, channel_names=public.channel_names,
                                      feature_valid=valid)
    copied_contract = deepcopy(public.contract)
    copied_contract["kernel_model"]["kernel_sizes"].append(9)
    assert public.contract["kernel_model"]["kernel_sizes"] == [3, 5]
    destination = public.save(tmp_path / "saved" / "mixed.pt")
    reloaded = WildfireModel.from_checkpoint(destination)
    actual = reloaded.predict_details(burned, environment, channel_names=reloaded.channel_names,
                                       feature_valid=valid)
    _assert_prediction_equal(expected, actual)
    saved = torch.load(destination, weights_only=True)
    assert saved["contract"] == public.contract
    assert saved["best_epoch"] == 11 and saved["validation_brier"] == 0.03
    assert saved["configuration"] == {"seed": 193}
    with pytest.raises(FileExistsError):
        public.save(destination)


def test_mixed_heat_checkpoint_and_resident_api_keep_predictor_provenance(mixed_checkpoint, mixed_inputs):
    public = load_model(mixed_checkpoint)
    physical = {
        "grid": AffineGrid.from_cell_size(10),
        "combustion": CombustionParameters(1, 18e6, 900),
        "radiative_fraction": 0.3, "emission_height_m": 5,
    }
    resident_heat = public.heat_model(**physical)
    loaded_heat = WildfireHeatModel.from_checkpoint(mixed_checkpoint, **physical)
    assert resident_heat.predictor is public.predictor
    for heat in (resident_heat, loaded_heat):
        assert heat.predictor_provenance["architecture"] == "MixedNonnegativeKernel"
        assert heat.predictor_provenance["checkpoint_sha256"] == public.checkpoint_sha256
        assert heat.predictor_provenance["best_epoch"] == 11
        assert heat.predictor_provenance["channel_names"] == ["fixture.a", "fixture.b"]
    burned, environment, valid = mixed_inputs
    expected = public.predict_details(burned, environment, channel_names=public.channel_names,
                                      feature_valid=valid)
    result = loaded_heat.predict_details(burned, environment, channel_names=public.channel_names,
                                         feature_valid=valid)
    np.testing.assert_allclose(result.new_burn_probability,
                               expected.probability[0].numpy(), equal_nan=True)
    np.testing.assert_array_equal(result.original_probability_valid, expected.valid[0].numpy())
    assert result.metadata["predictor"]["architecture"] == "MixedNonnegativeKernel"


@pytest.mark.parametrize("architecture", ["EnvironmentConditionedConvolution", "LearnedNonnegativeKernel"])
def test_package_dispatch_keeps_old_loader_dynamic(tmp_path, monkeypatch, architecture):
    import wildfire.inference as inference
    from wildfire.inference import load_trained_model

    path = tmp_path / "existing.pt"
    torch.save({"contract": {"architecture": architecture}}, path)
    expected = object()
    calls = []

    def loader(selected_path, *, device):
        calls.append((selected_path, device))
        return expected

    monkeypatch.setattr(inference, 'load_single_trained_model', loader)
    assert load_trained_model(path, device="cpu") is expected
    assert calls == [(path, "cpu")]


def test_mixed_public_api_dispatches_to_new_loader(tmp_path, monkeypatch):
    import wildfire.inference as mixed_inference

    path = tmp_path / "mixed.pt"
    contract = {"architecture": "MixedNonnegativeKernel"}
    torch.save({"contract": contract}, path)
    predictor = SimpleNamespace(contract=contract)
    calls = []

    def loader(selected_path, *, device):
        calls.append((selected_path, str(device)))
        return predictor

    monkeypatch.setattr(mixed_inference, "load_mixed_trained_model", loader)
    model = load_model(path)
    assert model.predictor is predictor and model.family == "exponential"
    assert calls == [(path.resolve(), "cpu")]


def test_existing_public_imports_do_not_eagerly_load_mixed_model_or_training():
    code = "\nimport sys\nfrom wildfire import WildfireModel\nfrom wildfire import load_model\nassert 'wildfire.search' not in sys.modules\n"
    subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[2], check=True)
