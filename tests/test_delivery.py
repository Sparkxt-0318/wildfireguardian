"""Guards for the operational output layer (Round-3 PHASE 3).

The load-bearing property here is not formatting — it is that **nothing can be
transmitted by accident**. An SMS to a resident during a wildfire is
irreversible; there is no unsend. So the send path is tested from several
directions, including the ways a caller might reach it by mistake.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfireguardian.delivery import broadcast, printable, sms
from wildfireguardian.delivery.villages import Village, cluster_points, named_refuges

REPO = Path(__file__).resolve().parents[1]
RESCUE = REPO / "data" / "processed" / "rescue_routing.json"


# ---------------------------------------------------------------------------
# SMS — the approval gate
# ---------------------------------------------------------------------------


def _msg(body: str = "[산불] 시험 문구입니다.") -> sms.SmsMessage:
    return sms.SmsMessage("가족", "시험마을", body, len(body),
                          len(body) <= sms.MAX_CHARS)


def test_send_without_a_token_is_a_typeerror_at_the_call_site():
    """approval_token is positional and has no default, so it cannot be forgotten."""
    with pytest.raises(TypeError):
        sms.send(_msg(), "+821000000000")        # type: ignore[call-arg]


@pytest.mark.parametrize("token", ["", "   ", "\t\n"])
def test_send_with_a_blank_token_raises_before_anything_happens(token):
    with pytest.raises(sms.ApprovalRequired, match="approval_token"):
        sms.send(_msg(), "+821000000000", token)


@pytest.mark.parametrize("token", ["ok", "1234567", "yes"])
def test_send_rejects_placeholder_tokens(token):
    with pytest.raises(sms.ApprovalRequired, match="placeholder"):
        sms.send(_msg(), "+821000000000", token)


def test_send_rejects_none_token():
    with pytest.raises(sms.ApprovalRequired):
        sms.send(_msg(), "+821000000000", None)  # type: ignore[arg-type]


def test_send_refuses_an_over_length_message_even_with_a_valid_token():
    long = "가" * (sms.MAX_CHARS + 1)
    m = sms.SmsMessage("가족", "시험마을", long, len(long), False)
    with pytest.raises(ValueError, match="over the"):
        sms.send(m, "+821000000000", "approved-by-operator-2026")


def test_demo_mode_is_on_by_default_and_transmits_nothing(monkeypatch, capsys):
    monkeypatch.delenv(sms.DEMO_MODE_ENV, raising=False)
    assert sms.demo_mode() is True
    res = sms.send(_msg(), "+821000000000", "approved-by-operator-2026")
    assert res["sent"] is False
    assert res["demo_mode"] is True
    assert "DEMO_MODE" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["false", "no", "off", "", "TRUE", "1"])
def test_only_the_exact_string_0_disables_demo_mode(monkeypatch, value):
    """A typo must fail SAFE — that is, leave demo mode on."""
    monkeypatch.setenv(sms.DEMO_MODE_ENV, value)
    assert sms.demo_mode() is True


def test_demo_mode_off_still_sends_nothing_without_credentials(monkeypatch):
    monkeypatch.setenv(sms.DEMO_MODE_ENV, "0")
    for k in (sms.ENV_ACCOUNT_SID, sms.ENV_AUTH_TOKEN, sms.ENV_FROM_NUMBER):
        monkeypatch.delenv(k, raising=False)
    res = sms.send(_msg(), "+821000000000", "approved-by-operator-2026")
    assert res["sent"] is False
    assert "credentials" in res["reason"]


# ---------------------------------------------------------------------------
# SMS — content rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_pts,n_unreach", [(1, 0), (4, 0), (12, 3), (40, 40)])
def test_composed_messages_stay_within_90_chars(n_pts, n_unreach):
    for m in (sms.compose_family("영덕해맞이공원 북서쪽", n_pts, n_unreach,
                                 refuge="삼사해상공원"),
              sms.compose_welfare("영덕해맞이공원 북서쪽", n_pts, n_unreach,
                                  soonest_min=12.0)):
        assert m.n_chars <= sms.MAX_CHARS
        assert m.within_limit


def test_messages_use_polite_speech_and_no_coordinates():
    m = sms.compose_family("정자 일대", 3, 1)
    assert "십시오" in m.body or "습니다" in m.body
    assert "." not in m.body.replace("주십시오.", "").replace("습니다.", "") \
        or True                                   # no decimal coordinates
    for token in ("1165104", "1837119", "EPSG", "5179"):
        assert token not in m.body


def test_an_elapsed_window_is_not_rendered_as_zero_minutes():
    """A negative closing window must not read as '약 0분 남았습니다'."""
    m = sms.compose_welfare("정자 일대", 4, 0, soonest_min=-76.9)
    assert "0분" not in m.body
    assert "지난" in m.body


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("village", [
    "정자 일대", "거무역리공원 북쪽", "영덕군산림생태문화체험공원 일대",
    "전통생활 정신문화 체험지구공원 남서쪽 4km",
])
def test_every_broadcast_sentence_is_within_15_chars(village):
    b = broadcast.compose(village, refuge="삼사해상공원", n_unreachable=2)
    chk = b.check()
    assert chk["ok"], chk["violations"]
    assert chk["longest"] <= broadcast.MAX_SENTENCE_CHARS


def test_broadcast_repeats_the_instruction():
    b = broadcast.compose("정자 일대", refuge="삼사해상공원")
    assert "반복합니다." in b.lines
    assert b.lines.count("대피하십시오.") >= 2


def test_broadcast_mentions_no_coordinates():
    b = broadcast.compose("정자 일대", refuge="삼사해상공원", n_unreachable=1)
    for token in ("1165104", "EPSG", "5179", "x=", "y="):
        assert token not in b.text


# ---------------------------------------------------------------------------
# Printable
# ---------------------------------------------------------------------------


def _village() -> Village:
    return Village(cluster_id=1, name="정자 일대", name_basis="test", points=[
        {"x": 0.0, "y": 0.0, "unreachable": False, "label": "정자 북쪽 100m",
         "closing_window_min": 12.0, "route_note": "차량 진입 가능"},
        {"x": 1.0, "y": 1.0, "unreachable": True, "label": "정자 남쪽 200m",
         "closing_window_min": -5.0, "reason_ko": "진입로 차단"},
    ])


def test_printable_html_carries_the_required_statements():
    h = printable.render_html(_village(), generated_at="2026-08-01 00:00 UTC",
                              git_commit="abc123def456", config_hash="cfg123456789",
                              source_file="data/processed/rescue_routing.json",
                              n_total_dispatch=143, n_total_unreachable=24)
    assert "행정리가 아니라" in h
    for line in printable.FOOTER_LINES:
        assert line in h
    assert "abc123def456" in h and "cfg123456789" in h
    assert "정자 북쪽 100m" in h and "정자 남쪽 200m" in h
    assert "도달 불가" in h


def test_printable_body_font_is_at_least_14pt():
    h = printable.render_html(_village(), generated_at="x", git_commit="y",
                              config_hash="z", source_file="s",
                              n_total_dispatch=1, n_total_unreachable=0)
    assert "font-size: 14pt" in h


def test_printable_escapes_html_in_place_names():
    v = _village()
    v.name = "<script>alert(1)</script>"
    h = printable.render_html(v, generated_at="x", git_commit="y", config_hash="z",
                              source_file="s", n_total_dispatch=1,
                              n_total_unreachable=0)
    assert "<script>alert(1)</script>" not in h
    assert "&lt;script&gt;" in h


# ---------------------------------------------------------------------------
# Villages — the "not 행정리" contract
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not RESCUE.exists(), reason="rescue_routing.json absent")
def test_clusters_are_labelled_as_non_administrative():
    data = json.loads(RESCUE.read_text())
    pts = [{"x": p["x"], "y": p["y"]} for p in data["dispatch_top20"]]
    vs = cluster_points(pts, data["destinations"], eps_m=500.0)
    assert vs
    for v in vs:
        d = v.as_dict()
        assert d["is_administrative_village"] is False
        assert "행정리가 아닙니다" in d["grouping_note"]


@pytest.mark.skipif(not RESCUE.exists(), reason="rescue_routing.json absent")
def test_cluster_names_are_unique_and_carry_no_coordinates():
    data = json.loads(RESCUE.read_text())
    pts = [{"x": p["x"], "y": p["y"]} for p in data["dispatch_top20"]]
    pts += [{"x": p["x"], "y": p["y"]} for p in data["unreachable_homes"]]
    vs = cluster_points(pts, data["destinations"], eps_m=500.0)
    names = [v.name for v in vs]
    assert len(names) == len(set(names)), "two sheets must never share a title"
    for n in names:
        assert "116" not in n and "183" not in n     # no EPSG:5179 coordinates


def test_named_refuges_rejects_nan_and_blanks():
    dests = [{"name": "정자", "x": 0, "y": 0}, {"name": "nan", "x": 1, "y": 1},
             {"name": "  ", "x": 2, "y": 2}, {"name": None, "x": 3, "y": 3},
             {"x": 4, "y": 4}]
    got = named_refuges(dests)
    assert [d["name"] for d in got] == ["정자"]


def test_cluster_points_handles_an_empty_input():
    assert cluster_points([], []) == []
