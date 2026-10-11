"""Training integration: input rarity changes fitting, never population scoring."""

import json

import numpy as np
import pytest
import torch

from wildfire import TrainingConfig
from wildfire import WildfireModel
from wildfire.cache import CachedSplit
from wildfire.cache import fit_normalization
from wildfire.metrics import fit_categorical_balance
from wildfire.metrics import brier
from wildfire.train import verify_run


def metadata(root):
    names = ['weather.temperature_2m', 'biome.biome_class=4', 'biome.biome_class=5', 'biome.biome_class=8']
    info = [dict(name=names[0], source_channel=names[0], encoding='continuous')]
    info += [dict(name=name, source_channel='biome.biome_class', encoding='one_hot',
                  categorical=True, class_code=code, class_name=f'Biome {code}')
             for name, code in zip(names[1:], (4, 5, 8))]
    return dict(channels=names, source_channels=[names[0], 'biome.biome_class'],
                channel_info=info, categorical_encoding='one_hot',
                categorical_classes={'biome.biome_class': [4, 5, 8]},
                channel_groups={names[0]: [0], 'biome.biome_class': [1, 2, 3]},
                kernel_size=3, dt_hours=1., data_root=str(root), source_files=[],
                event_ids=['train', 'validation', 'test'],
                splits={name: name for name in ('train', 'validation', 'test')},
                eligibility='at_least_one_burned_neighbor')


def data(event_index, shift=0.):
    n = 12
    environment = np.zeros((n, 4, 3, 3), dtype=np.float32)
    environment[:, 0] = np.arange(n * 9, dtype=np.float32).reshape(n, 3, 3) + shift
    environment[:, 2] = 1.
    # Both minority values exist only in context; every target center is biome5.
    environment[-2, 2, 0, 1] = 0.
    environment[-2, 1, 0, 1] = 1.
    environment[-1, 2, 0, 1] = 0.
    environment[-1, 3, 0, 1] = 1.
    burned = np.zeros((n, 1, 3, 3), dtype=np.float32)
    burned[:, 0, 0, 0] = 1.
    target = (np.arange(n) % 2).astype(np.float32)
    return CachedSplit(environment=environment, burned=burned, target=target,
                       weight=np.where(target == 1, 1., 4.).astype(np.float64),
                       event_index=np.full(n, event_index, dtype=np.int64),
                       time_utc=np.arange(n, dtype=np.int64) * 3600,
                       row=np.ones(n, dtype=np.int32), col=np.ones(n, dtype=np.int32))


def test_one_hot_normalization_remains_binary_without_changing_continuous_moments(tmp_path):
    split = data(0)
    original = fit_normalization(split)
    current = fit_normalization(split, metadata=metadata(tmp_path))
    np.testing.assert_array_equal(current[0][:1], original[0][:1])
    np.testing.assert_array_equal(current[1][:1], original[1][:1])
    np.testing.assert_array_equal(current[0][1:], np.zeros(3))
    np.testing.assert_array_equal(current[1][1:], np.ones(3))
    normalized = (split.environment - current[0][None, :, None, None]) / current[1][None, :, None, None]
    np.testing.assert_array_equal(normalized[:, 1:], split.environment[:, 1:])
    assert original[1][3] < .1


@pytest.mark.parametrize('mode', ['inverse-sqrt', 'none'])
def test_api_training_balances_context_inputs_and_independently_verifies_population_scores(tmp_path, mode):
    run = tmp_path / mode
    cache = run / 'prepared'
    cache.mkdir(parents=True)
    schema = metadata(tmp_path)
    (cache / 'metadata.json').write_text(json.dumps(schema))
    partitions = {name: data(index, shift=100. * index)
                  for index, name in enumerate(('train', 'validation', 'test'))}
    for name, split in partitions.items():
        np.savez_compressed(cache / f'{name}.npz', **vars(split))
    population_weights = partitions['train'].weight.copy()
    fitted = WildfireModel.train(cache, run / 'fitted', config=TrainingConfig(
        epochs=1, patience=1, batch_size=12, hidden_channels=2, threads=1,
        categorical_balance=mode,
    ))
    expected, audit = fit_categorical_balance(partitions['train'], schema, mode=mode)
    assert fitted.contract['categorical_balance'] == audit
    np.testing.assert_array_equal(partitions['train'].weight, population_weights)
    if mode == 'none':
        np.testing.assert_array_equal(expected, population_weights)
    else:
        assert expected[-1] > population_weights[-1]
        assert not np.array_equal(expected, population_weights)
    checkpoint = torch.load(run / 'fitted/checkpoint.pt', weights_only=True)
    assert checkpoint['train_optimization_weighted_prevalence'] == pytest.approx(
        np.dot(expected, partitions['train'].target) / expected.sum())
    np.testing.assert_array_equal(checkpoint['normalization_mean'][1:], np.zeros(3))
    np.testing.assert_array_equal(checkpoint['normalization_std'][1:], np.ones(3))
    for name, split in partitions.items():
        with np.load(run / f'fitted/{name}_predictions.npz') as predictions:
            np.testing.assert_array_equal(predictions['w'], split.weight)
            expected_brier = brier(split.target, predictions['p'], split.weight)
        recorded = fitted.training_metrics['splits'][name]['models']['learned_environment_kernel']['all_eligible']
        assert recorded['brier'] == expected_brier
        groups = fitted.training_metrics['splits'][name]['categorical_groups']
        assert groups['groups_overlap']
        assert groups['sources'][0]['classes'][2]['sample_count'] == 1
    verification = verify_run(run)
    assert verification['categorical_balance_reproduced_exactly']
    assert verification['optimization_statistics_reproduced']
    assert not verification['selection']['test_used_for_selection']
    # The independent verifier rejects a changed balancing audit.
    balance_path = run / 'fitted/categorical_balance.json'
    changed = json.loads(balance_path.read_text())
    changed['normalizer'] += .1
    balance_path.write_text(json.dumps(changed))
    with pytest.raises(AssertionError, match='audit differs'):
        verify_run(run)
    balance_path.write_text(json.dumps(audit))
    for key in ('mean_train_optimization_weight', 'train_optimization_weighted_prevalence'):
        changed_checkpoint = dict(checkpoint)
        changed_checkpoint[key] += .1
        torch.save(changed_checkpoint, run / 'fitted/checkpoint.pt')
        with pytest.raises(AssertionError, match='optimization statistic'):
            verify_run(run)
    torch.save(checkpoint, run / 'fitted/checkpoint.pt')


@pytest.mark.parametrize('options', [
    {'categorical_balance': 'unknown'}, {'categorical_balance_min_frequency': 0.},
    {'categorical_balance_min_frequency': float('nan')},
    {'categorical_balance_min_frequency': True}, {'categorical_balance_max_factor': .5},
    {'categorical_balance_max_factor': float('inf')},
])
def test_public_configuration_rejects_invalid_balance_settings(options):
    with pytest.raises(ValueError):
        TrainingConfig(**options)


def test_enabled_balancing_changes_fitted_parameters_with_same_data_and_seed(tmp_path):
    cache = tmp_path / 'prepared'
    cache.mkdir()
    (cache / 'metadata.json').write_text(json.dumps(metadata(tmp_path)))
    for index, name in enumerate(('train', 'validation', 'test')):
        np.savez_compressed(cache / f'{name}.npz', **vars(data(index)))
    checkpoints = {}
    for mode in ('none', 'inverse-sqrt'):
        WildfireModel.train(cache, tmp_path / mode, config=TrainingConfig(
            epochs=3, patience=3, batch_size=12, hidden_channels=2,
            threads=1, categorical_balance=mode,
        ))
        checkpoints[mode] = torch.load(tmp_path / mode / 'checkpoint.pt', weights_only=True)
    original, balanced = checkpoints['none'], checkpoints['inverse-sqrt']
    np.testing.assert_array_equal(original['normalization_mean'], balanced['normalization_mean'])
    np.testing.assert_array_equal(original['normalization_std'], balanced['normalization_std'])
    assert any(not torch.equal(value, balanced['model_state_dict'][name])
               for name, value in original['model_state_dict'].items())
