import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from wfg_impact import sources  # noqa: E402


def pytest_configure(config):
    # matplotlib 3.9.4 calls pyparsing APIs that pyparsing 3.3 marks deprecated; unrelated to these tests
    config.addinivalue_line('filterwarnings', 'ignore::DeprecationWarning:matplotlib')


def graphs_available() -> bool:
    return all(sources.graph_path(r).is_file() for r in sources.REGIONS)


@pytest.fixture(scope='session')
def path_a_result():
    if not graphs_available():
        pytest.skip('road graphs missing: run python tools/fetch_routing_inputs.py (SHA-verified release inputs)')
    from wfg_impact import analysis
    return analysis.run(with_graphs=True)


@pytest.fixture(scope='session')
def built(path_a_result):
    import compute
    return compute.build_outputs(path_a_result)
