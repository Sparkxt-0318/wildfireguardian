"""Offline-capability tests for the field view (Session 8 Phase 4).

The page must work with the network unplugged: no external URL, no CDN, no
tile server, no external font — the same contract as the console, checked
with the same exemption for XML namespace identifiers. And the wording
discipline is pinned: 연동을 "상정하여 설계" (designed on the assumption of
integration), never a claim of being integrated/connected/deployed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "web" / "field_view.html"

pytestmark = pytest.mark.skipif(not PAGE.exists(),
                                reason="web/field_view.html not built "
                                       "(python scripts/build_field_view.py)")

#: Namespace identifiers a browser never fetches (same list as api.guard).
_NS = {"http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"}


def _text() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_no_fetchable_external_reference():
    """Network unplugged: every URL-looking string is a namespace identifier."""
    text = _text()
    urls = set(re.findall(r"(?:https?|ftp|ws|wss|file)://[^\s\"'<>)\\]+", text))
    fetchable = {u for u in urls if u.rstrip("/") not in
                 {n.rstrip("/") for n in _NS}}
    assert not fetchable, fetchable
    # protocol-relative URLs are as fetchable as absolute ones
    assert not re.search(r'(?<![:\w/])//[a-z0-9][a-z0-9.-]*\.[a-z]{2,}/', text)
    # no external font / stylesheet / script
    assert '<link' not in text.lower()
    assert 'src="http' not in text.lower()


def test_svg_only_no_raster_tiles():
    text = _text()
    assert "<svg" in text
    for tag in ("<img", "<canvas", "<iframe", "tile", "openstreetmap.org"):
        assert tag not in text.lower(), tag


def test_required_elements_present():
    text = _text()
    for needle in ("모의 GPS", "화점", "등시선", "철수 트리거", "왕복 여유"):
        assert needle in text, needle
    # 30/60/90-min isochrones from the hazard sequence
    for m in ("30분", "60분", "90분"):
        assert m in text, m


def test_wording_discipline_assumed_not_claimed():
    text = _text()
    assert "재난안전통신망 연동을 상정하여 설계하였습니다" in text
    # never claimed as integrated / connected / deployed
    for phrase in ("연동되었습니다", "연동 완료", "접속되어", "배포되었습니다",
                   "운용 중입니다"):
        assert phrase not in text, phrase
    # planning-scale honesty is on the screen itself
    assert "위성 재방문 주기" in text
    # 합니다체, never 한다체 (no bare-한다 sentence endings)
    assert not re.search(r"한다\.", text)


def test_console_route_serves_it():
    """GET /field returns the page through the app (no preload needed)."""
    from fastapi.testclient import TestClient

    from wildfireguardian.api.app import create_app
    from wildfireguardian.service import jobs as _jobs
    from wildfireguardian.service import resources as _resources

    runner = _jobs.JobRunner(cache=_resources.ResourceCache(capacity=1),
                             max_workers=1, max_queue=4)
    app = create_app(runner=runner)
    try:
        with TestClient(app) as client:
            r = client.get("/field")
            assert r.status_code == 200
            assert "현장 보기" in r.text
    finally:
        runner.shutdown(wait=False)
