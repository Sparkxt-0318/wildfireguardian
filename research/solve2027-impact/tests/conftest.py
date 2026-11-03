import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from wfg_impact import sources  # noqa: E402


def pytest_configure(config):
    # matplotlib 3.9.4 calls pyparsing APIs that pyparsing 3.3 marks deprecated; unrelated to these tests
    config.addinivalue_line('filterwarnings', 'ignore::DeprecationWarning:matplotlib')


def routing_inputs_available() -> bool:
    """The road graphs AND the six HAZARD packets (tools/fetch_routing_inputs.py). Only the tests that need them skip
    without them; the cache-only numbers are recomputed and compared either way (tests/test_cache_only.py)."""
    return sources.routing_inputs_available()


ROUTING_SKIP = 'road graphs / HAZARD packets missing: run python tools/fetch_routing_inputs.py (SHA-verified release inputs)'


@contextmanager
def no_routing_data(tmp_dir: Path):
    """Point the package at a data/routing/ folder that does not exist, so that any read from it fails loudly."""
    old = os.environ.get('WFG_ROUTING_DATA')
    os.environ['WFG_ROUTING_DATA'] = str(tmp_dir / 'no-routing-data')
    try:
        assert not sources.routing_inputs_available()
        yield
    finally:
        if old is None:
            os.environ.pop('WFG_ROUTING_DATA', None)
        else:
            os.environ['WFG_ROUTING_DATA'] = old


@pytest.fixture(scope='session')
def path_a_result():
    if not routing_inputs_available():
        pytest.skip(ROUTING_SKIP)
    from wfg_impact import analysis
    return analysis.run(with_graphs=True)


@pytest.fixture(scope='session')
def built(path_a_result):
    import compute
    return compute.build_outputs(path_a_result)


@pytest.fixture(scope='session')
def cache_only_result(tmp_path_factory):
    """Path A records from the six cache files alone, with data/routing/ made unreachable (never skips)."""
    from wfg_impact import analysis
    with no_routing_data(tmp_path_factory.mktemp('cache-only')):
        return analysis.run(with_graphs=False)
