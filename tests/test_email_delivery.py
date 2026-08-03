"""Guards for the email delivery channel (Round-3 PHASE 7).

This is the first channel in the project that CAN actually transmit, so the
tests are about the gates rather than the formatting:

1. :func:`send` cannot be reached without an approval token.
2. It cannot be reached without ``dry_run=False`` being passed on purpose.
3. It cannot target any address other than ``DEMO_RECIPIENT``.
4. The approval script has **no code path** from argument parsing to a send
   that skips the typed confirmation — asserted against the AST, so a future
   edit that adds a ``--yes`` shortcut fails here.
5. The app password never reaches a log, an artifact, or an exception message.

The formatting tests that do exist check the two things a recipient depends on:
the fixed cautions are present, and the HTML uses inline styles only, because
Gmail strips ``<style>`` blocks.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
from pathlib import Path

import pytest

from wildfireguardian.delivery import email as em
from wildfireguardian.delivery import printable, sms

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "send_dispatch_email.py"

ENV = {em.ENV_ADDRESS: "sender@gmail.com",
       em.ENV_APP_PASSWORD: "abcd efgh ijkl mnop",
       em.ENV_RECIPIENT: "siyeong0318@gmail.com"}
ALLOWED = ENV[em.ENV_RECIPIENT]

POINTS = [
    {"label": "천전공원 남쪽 120m", "unreachable": False,
     "closing_window_min": 45.0, "route_note": "최단 경로는 화재 통과 — 우회 경로 필요"},
    {"label": "송이광장 동쪽 300m", "unreachable": True,
     "closing_window_min": -5.0, "reason_ko": "예산 내 안전한 보행 경로가 없음(우회 포함)"},
    {"label": "침수정 북쪽 900m", "unreachable": False,
     "closing_window_min": None, "route_note": "우회 경로 필요"},
]


def _draft(role: str = "복지사") -> em.EmailMessageDraft:
    fn = em.compose_welfare if role == "복지사" else em.compose_family
    return fn("시험마을", POINTS, refuge="시험공원",
              generated_at="2026-08-03 01:00 UTC",
              scope_lines=["화점 탐지: 실시간 (FIRMS NRT)",
                           "기상 자료: 2025-03-25 12:25 UTC 기준 "
                           "(ERA5는 약 5일 지연 발행)"],
              banner="■ 재생 모드 ■")


# ---------------------------------------------------------------------------
# 1. The approval token
# ---------------------------------------------------------------------------


def test_send_without_a_token_is_a_typeerror_at_the_call_site():
    with pytest.raises(TypeError):
        em.send(_draft(), ALLOWED)          # type: ignore[call-arg]


@pytest.mark.parametrize("token", ["", "   ", "\t\n"])
def test_send_with_a_blank_token_raises(token):
    with pytest.raises(em.ApprovalRequired, match="approval_token"):
        em.send(_draft(), ALLOWED, token, env=ENV)


def test_send_rejects_placeholder_tokens():
    with pytest.raises(em.ApprovalRequired, match="placeholder"):
        em.send(_draft(), ALLOWED, "ok", env=ENV)


def test_send_rejects_a_none_token():
    with pytest.raises(em.ApprovalRequired):
        em.send(_draft(), ALLOWED, None, env=ENV)  # type: ignore[arg-type]


def test_the_token_is_checked_before_the_recipient():
    """Order matters: a bad token must fail even for a forbidden address, so
    the failure cannot be probed to discover the allowed recipient."""
    with pytest.raises(em.ApprovalRequired):
        em.send(_draft(), "stranger@example.com", "", env=ENV)


# ---------------------------------------------------------------------------
# 2. DRY RUN is the default
# ---------------------------------------------------------------------------


def test_dry_run_is_the_default_and_transmits_nothing():
    def explode():
        raise AssertionError("SMTP was constructed during a dry run")

    r = em.send(_draft(), ALLOWED, "operator-confirmed-2026", env=ENV,
                smtp_factory=explode)
    assert r.sent is False and r.dry_run is True
    assert "DRY_RUN" in r.reason


def test_a_real_send_requires_dry_run_false_explicitly():
    sig = inspect.signature(em.send)
    assert sig.parameters["dry_run"].default is True
    assert sig.parameters["dry_run"].kind is inspect.Parameter.KEYWORD_ONLY


def test_without_credentials_a_real_send_still_transmits_nothing():
    env = dict(ENV)
    env.pop(em.ENV_APP_PASSWORD)

    def explode():
        raise AssertionError("SMTP was constructed with no app password")

    r = em.send(_draft(), ALLOWED, "operator-confirmed-2026", dry_run=False,
                env=env, smtp_factory=explode)
    assert r.sent is False
    assert em.ENV_APP_PASSWORD in r.reason


# ---------------------------------------------------------------------------
# 3. One recipient only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("addr", ["stranger@example.com", "siyeong0318@gmail.co",
                                  "a@b.c", "", "   "])
def test_any_other_recipient_is_refused_before_a_connection_opens(addr):
    def explode():
        raise AssertionError("SMTP was constructed for a forbidden recipient")

    with pytest.raises(em.RecipientNotAllowed):
        em.send(_draft(), addr, "operator-confirmed-2026", dry_run=False,
                env=ENV, smtp_factory=explode)


def test_the_allowed_recipient_is_matched_case_insensitively():
    r = em.send(_draft(), ALLOWED.upper(), "operator-confirmed-2026", env=ENV)
    assert r.dry_run is True                 # accepted, and still a dry run


def test_no_approved_recipient_configured_means_no_send():
    env = dict(ENV)
    env.pop(em.ENV_RECIPIENT)
    with pytest.raises(em.RecipientNotAllowed, match=em.ENV_RECIPIENT):
        em.send(_draft(), ALLOWED, "operator-confirmed-2026", env=env)


def test_a_refusal_message_never_prints_a_full_address():
    with pytest.raises(em.RecipientNotAllowed) as exc:
        em.send(_draft(), "stranger@example.com", "operator-confirmed-2026",
                env=ENV)
    assert ALLOWED not in str(exc.value)
    assert "stranger@example.com" not in str(exc.value)


# ---------------------------------------------------------------------------
# 4. The script has no path to a send that skips the confirmation
# ---------------------------------------------------------------------------


def _script_tree() -> ast.Module:
    return ast.parse(SCRIPT.read_text(encoding="utf-8"))


def _calls(node) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        f, parts = n.func, []
        while isinstance(f, ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            parts.append(f.id)
        if parts:
            out.add(".".join(reversed(parts)))
    return out


def test_the_script_calls_send_exactly_once():
    """One call site is what makes the gate auditable. Two is how one gets
    forgotten."""
    tree = _script_tree()
    sends = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "send"]
    assert len(sends) == 1, f"expected 1 em.send call site, found {len(sends)}"


def test_dry_run_false_is_never_hardcoded_at_the_call_site():
    """The single send passes a VARIABLE, whose only False assignment is the
    line immediately after the confirmation returns."""
    tree = _script_tree()
    send = next(n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "send")
    kw = {k.arg: k.value for k in send.keywords}
    assert "dry_run" in kw
    assert not isinstance(kw["dry_run"], ast.Constant), (
        "dry_run must be a variable gated by the confirmation, never a literal")


def test_every_assignment_of_dry_run_false_follows_the_confirmation():
    """`dry_run = False` may appear only in the branch that has just called
    confirm_or_abort. A future --yes shortcut fails this test."""
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    falses = [n for n in ast.walk(main)
              if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "dry_run"
                      for t in n.targets)
              and isinstance(n.value, ast.Constant) and n.value.value is False]
    assert len(falses) == 1, "exactly one place may arm the send"
    (assign,) = falses
    enclosing = [n for n in ast.walk(main)
                 if isinstance(n, ast.If) and any(
                     stmt is assign for stmt in ast.walk(n))]
    assert enclosing, "the arming assignment must sit inside a branch"
    guarded = any("confirm_or_abort" in _calls(branch) for branch in enclosing)
    assert guarded, ("dry_run = False must be reachable only after "
                     "confirm_or_abort() has run")


def test_the_confirmation_requires_a_whole_word_not_a_keystroke():
    assert "발송확인" in em_script_words()
    assert all(len(w) >= 4 for w in _confirm_words()), (
        "a single keystroke is too easy to give by reflex")


def _confirm_words() -> tuple[str, ...]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_sde", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.CONFIRM_WORDS


def em_script_words() -> tuple[str, ...]:
    return _confirm_words()


def test_the_script_never_constructs_an_approval_token_outside_confirmation():
    """Only confirm_or_abort may mint a token, and only after input()."""
    tree = _script_tree()
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "confirm_or_abort")
    assert "input" in _calls(fn), "the confirmation must actually block on input"
    src = SCRIPT.read_text(encoding="utf-8")
    assert src.count("operator-confirmed-") == 1, (
        "the token prefix may appear only where the confirmation mints it")


# ---------------------------------------------------------------------------
# 5. The app password never escapes
# ---------------------------------------------------------------------------


def test_credentials_present_does_not_return_the_password():
    assert em.credentials_present(ENV) is True
    assert isinstance(em.credentials_present(ENV), bool)


def test_no_function_here_returns_the_app_password():
    src = inspect.getsource(em)
    assert "return password" not in src
    assert f'return src.get("{em.ENV_APP_PASSWORD}"' not in src


def test_an_smtp_failure_scrubs_the_password_from_the_error():
    password = ENV[em.ENV_APP_PASSWORD]

    class Boom:
        def __enter__(self):
            raise RuntimeError(f"535 auth failed for {password}")

        def __exit__(self, *a):
            return False

    r = em.send(_draft(), ALLOWED, "operator-confirmed-2026", dry_run=False,
                env=ENV, smtp_factory=Boom)
    assert r.sent is False
    assert password not in r.error
    assert "<REDACTED>" in r.error


def test_the_send_record_masks_the_recipient_and_records_no_credentials():
    r = em.send(_draft(), ALLOWED, "operator-confirmed-2026", env=ENV)
    blob = json.dumps(r.as_dict(), ensure_ascii=False)
    assert ALLOWED not in blob
    assert "s***0318@gmail.com" in blob
    assert ENV[em.ENV_APP_PASSWORD] not in blob
    assert r.as_dict()["credentials_recorded"] is False


@pytest.mark.parametrize("addr,expected", [
    ("siyeong0318@gmail.com", "s***0318@gmail.com"),
    ("abc@x.io", "a***@x.io"),
    ("notanemail", "***"),
])
def test_mask_address(addr, expected):
    assert em.mask_address(addr) == expected


# ---------------------------------------------------------------------------
# 6. Content the recipient depends on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["가족", "복지사"])
def test_both_bodies_carry_the_two_fixed_cautions(role):
    d = _draft(role)
    for line in printable.FOOTER_LINES:
        assert line in d.text_body, line
        assert line in d.html_body, line


@pytest.mark.parametrize("role", ["가족", "복지사"])
def test_both_bodies_carry_the_coverage_caveat(role):
    d = _draft(role)
    assert "32.6 %만 덮는" in d.text_body
    assert "32.6 %만 덮는" in d.html_body


@pytest.mark.parametrize("role", ["가족", "복지사"])
def test_both_bodies_carry_the_scope_statement(role):
    d = _draft(role)
    for body in (d.text_body, d.html_body):
        assert "화점 탐지: 실시간 (FIRMS NRT)" in body
        assert "ERA5는 약 5일 지연 발행" in body
        assert "재생 모드" in body


def test_the_subject_has_the_required_shape():
    d = _draft()
    assert d.subject.startswith("[산불 대피 안내] 시험마을 — ")
    assert em.subject_for("마을", "2026-01-01 00:00 UTC") == \
        "[산불 대피 안내] 마을 — 2026-01-01 00:00 UTC"


def test_the_welfare_message_flags_an_elapsed_window():
    d = _draft("복지사")
    assert "이미 경과" in d.text_body
    assert "시한이 지난 곳이 1곳" in d.text_body


def test_the_family_message_names_the_refuge_and_the_count():
    d = _draft("가족")
    assert "시험공원" in d.text_body
    assert "3곳" in d.text_body


def test_an_absent_window_is_not_called_unknown():
    """In the 459 series an absent window is a positive statement — the place
    never reaches the cutoff inside the horizon — not a gap in the data."""
    d = _draft()
    assert em.NO_WINDOW_LABEL in d.text_body
    assert "확인 불가" not in d.text_body
    assert "알 수 없다는 뜻이 아닙니다" in d.text_body


def test_the_html_uses_inline_styles_only_because_gmail_strips_style_blocks():
    d = _draft()
    assert "<style" not in d.html_body.lower()
    assert "</style>" not in d.html_body.lower()
    assert "@media" not in d.html_body
    assert 'style="' in d.html_body
    assert "<link" not in d.html_body.lower()
    assert "<script" not in d.html_body.lower()


def test_the_html_embeds_no_remote_assets():
    """A wildfire notice must render with images blocked and no network."""
    assert not re.search(r'src\s*=\s*"https?://', _draft().html_body)
    assert "<img" not in _draft().html_body.lower()


def test_the_html_escapes_place_names():
    pts = [{"label": "<script>x</script> 마을", "unreachable": False,
            "closing_window_min": 10.0, "route_note": "확인"}]
    d = em.compose_family("<b>마을</b>", pts, generated_at="t", scope_lines=[])
    assert "<script>" not in d.html_body
    assert "&lt;script&gt;" in d.html_body


def test_the_mime_message_is_multipart_alternative_with_both_bodies():
    msg = em.build_mime(_draft(), ALLOWED, "sender@gmail.com")
    assert msg.get_content_type() == "multipart/alternative"
    types = {p.get_content_type() for p in msg.walk()}
    assert {"text/plain", "text/html"} <= types
    assert msg["To"] == ALLOWED
    assert msg["Subject"].startswith("[산불 대피 안내]")


def test_no_coordinates_reach_the_recipient():
    for body in (_draft("가족").text_body, _draft("복지사").html_body):
        assert not re.search(r"\b1\d{6}\.?\d*\s*,\s*1\d{6}", body)


# ---------------------------------------------------------------------------
# 7. The SMS channel is untouched and still cannot send
# ---------------------------------------------------------------------------


def test_the_sms_module_still_exists_and_stays_in_demo_mode(monkeypatch):
    monkeypatch.delenv(sms.DEMO_MODE_ENV, raising=False)
    assert sms.demo_mode() is True
    assert hasattr(sms, "send") and hasattr(sms, "compose_family")


def test_the_email_module_does_not_reuse_the_sms_send_path():
    assert "sms" not in _calls(ast.parse(inspect.getsource(em)))
