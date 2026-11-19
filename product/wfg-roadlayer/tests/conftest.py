"""Shared fixtures. The data cache is $WFG_ROADLAYER_CACHE or ~/.cache/wfg-roadlayer; tests that need it skip with a
reason when `python -m wfg_roadlayer setup` has not been run (and cannot be run from local files)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
sys.path.insert(0, str(PRODUCT))

from wfg_roadlayer import cli, regiondata  # noqa: E402
from wfg_roadlayer.errors import Refusal  # noqa: E402


def _cache_ready(cache: Path) -> bool:
    try:
        regiondata.font_paths(cache)
        for rid in regiondata.REGISTRY["regions"]:
            regiondata._cached(cache, "graphs/%s/graph.json" % rid, regiondata.REGISTRY["regions"][rid]["graph"]["sha256"], "", "")
        return True
    except Refusal:
        return False


@pytest.fixture(scope="session")
def cache():
    c = regiondata.default_cache()
    if not _cache_ready(c):
        try:
            regiondata.setup(c, log=lambda *_: None)
        except BaseException as exc:  # no network and no local copies
            pytest.skip("data cache not set up and setup failed (%s); run: python -m wfg_roadlayer setup" % exc)
    os.environ["WFG_ROADLAYER_CACHE"] = str(c)
    return c


@pytest.fixture(scope="session")
def example_out(cache, tmp_path_factory):
    """The worked example, run once per test session through the same command a user types."""
    out = tmp_path_factory.mktemp("example") / "wfg-roadlayer-example"
    t0 = time.perf_counter()
    code = cli.main(["example", "--out", str(out), "--cache", str(cache)])
    assert code == 0
    return {"path": out, "wall_s": time.perf_counter() - t0}
