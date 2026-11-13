"""Ledger row 85 regression: the wind gate tests each location on its own (D0_RULE amendment 1).

The verifier's example: place mean 6 / gust 6 m/s, site mean 1 / gust 13 m/s. The site's own gust spread is 12 m/s,
over 15 kt (7.72 m/s), so the row is excluded. The old behaviour (max mean and max gust taken separately, then
subtracted: 13 - 6 = 7) does not exclude, and this test fails on it.
"""
import datetime as dt
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('build_d0', Path(__file__).resolve().parents[1] / 'build_d0.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

T = dt.datetime(2025, 3, 25, 6, 0, tzinfo=dt.timezone.utc)
HOUR = '2025-03-25T06:00'
PLACE, SITE = (36.4000, 129.3000), (36.5000, 129.4000)


def wind(place, site):
    def rec(ws, wg):
        return {'time': [HOUR], 'wind_speed_10m': [ws], 'wind_gusts_10m': [wg]}
    return {'points': {f'{PLACE[0]:.4f},{PLACE[1]:.4f}': rec(*place), f'{SITE[0]:.4f},{SITE[1]:.4f}': rec(*site)}}


def old_behaviour(w):
    vals = [(w['points'][k]['wind_speed_10m'][0], w['points'][k]['wind_gusts_10m'][0]) for k in w['points']]
    ws, wg = max(v[0] for v in vals), max(v[1] for v in vals)
    return ws > b.LIM12 or wg - ws > b.SPREAD


def test_per_location_spread_excludes():
    w = wind((6.0, 6.0), (1.0, 13.0))
    r = b.wind_at(w, PLACE, SITE, T)
    assert r['over_type12'] is True
    assert [p['point'] for p in r['points']] == ['place', 'site']
    assert r['points'][1]['gust_spread_ms'] == 12.0
    assert old_behaviour(w) is False          # the defect this test guards against


def test_calm_not_excluded_and_near_limit_flag():
    r = b.wind_at(wind((3.0, 5.0), (2.0, 2.0 + b.SPREAD - 0.05)), PLACE, SITE, T)
    assert r['over_type12'] is False and r['near_limit'] is True


def test_mean_over_limit_at_one_point():
    r = b.wind_at(wind((b.LIM12 + 0.5, b.LIM12 + 1.0), (1.0, 1.0)), PLACE, SITE, T)
    assert r['over_type12'] is True and r['points'][0]['over_type12'] and not r['points'][1]['over_type12']
