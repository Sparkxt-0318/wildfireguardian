"""Email delivery to family members and welfare workers.

Round-3 PHASE 7.

WHY EMAIL, AND WHY NOW
----------------------
The Twilio trial account cannot verify a Korean mobile number without an
account upgrade, so SMS stays in ``DEMO_MODE`` (see
``docs/delivery_channels.md``). Email is a legitimate channel for the same two
audiences — a family member and a 복지사 both read email — and it is the one
channel this project can actually exercise end to end. So the approval design
is carried over unchanged rather than relaxed for a channel that happens to
work.

THE SAFETY MODEL — read before changing anything here
-----------------------------------------------------
This module CAN send. That is the difference from :mod:`.sms`, and it is why
the gates are stricter rather than looser:

1. :func:`send` takes ``approval_token`` as a **positional, mandatory**
   argument. ``send(msg, addr)`` is a ``TypeError`` at the call site; a blank
   or placeholder token raises :class:`ApprovalRequired`. Both fire before any
   SMTP object is constructed.
2. **DRY_RUN is the default.** ``send`` transmits only when
   ``dry_run=False`` is passed explicitly. Nothing infers it.
3. **One recipient, enforced in code.** Every send is checked against
   ``DEMO_RECIPIENT``; any other address raises
   :class:`RecipientNotAllowed` before a connection is opened. This is not a
   convention — a wrong address on a wildfire evacuation notice is
   irreversible, and there is no unsend.
4. **The app password is read from the environment and never leaves it.** It is
   not logged, not written into any artifact, not placed in an exception
   message, and not returned by any function here. :func:`credentials_present`
   answers the only question a caller ever needs to ask about it.
5. Recipients are **masked** in every record (``s***0318@gmail.com``).

WHAT CHANGED IN THE PROJECT'S SAFETY CLAIM
------------------------------------------
The old statement — "delivery is simulated and nothing is ever sent" — is no
longer true of this channel and must not be repeated. The accurate statement,
which ``docs/delivery_channels.md`` now carries, is:

    전달 문구는 자동으로 발송되지 않으며, 승인 권한을 가진 사람이 명시적으로
    확인한 뒤에만 발송됩니다. 발송 함수는 승인 토큰 없이 호출될 수 없습니다.

GMAIL AND HTML
--------------
Gmail strips ``<style>`` blocks, so every rule here is an inline ``style=``
attribute on the element it applies to. No external CSS, no web fonts, no
images: the message must render in a plain client, in monochrome, for someone
reading on a phone at night.
"""

from __future__ import annotations

import html as _html
import os
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

#: Environment variables. Values are read, never logged.
ENV_ADDRESS = "GMAIL_ADDRESS"
ENV_APP_PASSWORD = "GMAIL_APP_PASSWORD"
ENV_RECIPIENT = "DEMO_RECIPIENT"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465                      # implicit TLS; no STARTTLS upgrade race

#: The two fixed cautions, identical to the A4 sheet's footer. Imported rather
#: than retyped so the paper and the email can never drift apart.
from .printable import FOOTER_LINES  # noqa: E402

#: Carried by every absolute Yeongdeok count that reaches a recipient.
#: docs/HANDOFF_ROUND3.md §2-A is the decision record.
COVERAGE_CAVEAT_KO: str = (
    "영덕 수치는 정본 화재 핵심의 32.6 %만 덮는 보행망에서 산출되었습니다. "
    "나머지 3분의 2에 있는 출발지들의 거동은 측정되지 않았으며, 편향의 방향도 "
    "알려져 있지 않습니다.")

SENDER_NAME = "WildfireGuardian 대피 안내"


class ApprovalRequired(RuntimeError):
    """Raised when :func:`send` is called without a usable approval token."""


class RecipientNotAllowed(RuntimeError):
    """Raised when a send targets any address other than ``DEMO_RECIPIENT``."""


class CredentialsMissing(RuntimeError):
    """Raised when a real send is requested with no app password configured."""


def gmail_address(env: dict[str, str] | None = None) -> str:
    return ((env or os.environ).get(ENV_ADDRESS) or "").strip()


def allowed_recipient(env: dict[str, str] | None = None) -> str:
    """The single address this module may ever send to."""
    return ((env or os.environ).get(ENV_RECIPIENT) or "").strip()


def credentials_present(env: dict[str, str] | None = None) -> bool:
    """True when a real send is possible. Never reveals the password itself."""
    src = env or os.environ
    return bool((src.get(ENV_ADDRESS) or "").strip()
                and (src.get(ENV_APP_PASSWORD) or "").strip())


def mask_address(addr: str) -> str:
    """``siyeong0318@gmail.com`` -> ``s***0318@gmail.com``.

    Keeps enough to confirm the right mailbox was used and not enough to
    reconstruct it. Applied to every address that reaches an artifact.
    """
    a = (addr or "").strip()
    if "@" not in a:
        return "***"
    local, _, domain = a.partition("@")
    if len(local) <= 5:
        return f"{local[:1]}***@{domain}"
    return f"{local[:1]}***{local[-4:]}@{domain}"


def smtp_reachable(host: str = SMTP_HOST, port: int = SMTP_PORT,
                   timeout_s: float = 8.0) -> tuple[bool, str]:
    """Can a TCP connection to the SMTP port even be opened?

    Worth asking separately, because the two failures look identical in a
    traceback and mean opposite things: a connect timeout is the NETWORK
    refusing outbound SMTP, while a 535 is the CREDENTIAL being rejected.
    Reporting the first as if it were the second would send someone to
    regenerate a perfectly good app password.

    Many networks — corporate, campus, and most Korean consumer ISPs — block
    outbound 25/465/587 wholesale to limit spam relays. That is a property of
    where the machine is, not of this code.
    """
    import socket

    s = socket.socket()
    s.settimeout(timeout_s)
    try:
        s.connect((host, port))
        return True, "reachable"
    except TimeoutError:
        return False, (f"{host}:{port} did not answer within {timeout_s:g}s — "
                       "outbound SMTP appears to be blocked on this network. "
                       "This is NOT a credential problem.")
    except OSError as exc:
        return False, f"{host}:{port} unreachable ({type(exc).__name__})"
    finally:
        s.close()


def _classify_smtp_error(exc: BaseException) -> str:
    """Network condition, or credential rejection? Say which."""
    if isinstance(exc, TimeoutError):
        return ("network: the SMTP port did not answer. Outbound SMTP is "
                "blocked on this network. The credentials were never "
                "presented, so nothing about them is implied.")
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return ("credential: the server rejected the app password. Regenerate "
                "it at https://myaccount.google.com/apppasswords .")
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "recipient: the server refused the address."
    if isinstance(exc, (ConnectionRefusedError, OSError)):
        return ("network: the connection could not be established. The "
                "credentials were never presented.")
    return "unclassified"


def _check_token(approval_token: object) -> None:
    if not isinstance(approval_token, str) or not approval_token.strip():
        raise ApprovalRequired(
            "email send requires a non-empty approval_token. A wildfire "
            "evacuation notice is irreversible; there is no unsend. Obtain "
            "explicit human approval and pass its token.")
    if len(approval_token.strip()) < 8:
        raise ApprovalRequired(
            "approval_token looks like a placeholder (under 8 characters). "
            "Refusing to send.")


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmailMessageDraft:
    """One rendered message, with the audit fields an operator would need."""

    recipient_role: str              # "가족" | "복지사"
    village: str
    subject: str
    text_body: str
    html_body: str
    n_points: int
    n_unreachable: int
    generated_at: str

    def as_dict(self, *, include_bodies: bool = False) -> dict:
        d = {
            "recipient_role": self.recipient_role,
            "village": self.village,
            "subject": self.subject,
            "n_points": self.n_points,
            "n_unreachable": self.n_unreachable,
            "generated_at": self.generated_at,
            "text_chars": len(self.text_body),
            "html_chars": len(self.html_body),
        }
        if include_bodies:
            d["text_body"] = self.text_body
            d["html_body"] = self.html_body
        return d


def subject_for(village: str, generated_at: str) -> str:
    return f"[산불 대피 안내] {village} — {generated_at}"


#: The simulated horizon of the canonical hazard field, in hours. A location
#: with no closing window did not reach the impassable probability within it.
HORIZON_H: int = 12

#: What an ABSENT closing window means in the 459 series.
#:
#: ⚠ It does NOT mean "unknown". `_time_to_cutoff` walks the field's five time
#: slices (0…720 min) and returns infinity when the location never reaches
#: p >= 0.5 — a positive statement about the prediction, not a gap in it. The
#: A4 sheet renders the same absence as "확인 불가", which was correct for the
#: 439 series (where it really was unknown) and reads as a hedge here. The A4
#: layer is out of scope for PHASE 7 and is NOT edited; the divergence is
#: recorded in docs/delivery_channels.md instead of being papered over.
NO_WINDOW_LABEL: str = f"{HORIZON_H}시간 내 미도달"


def _fmt_remaining(v) -> str:
    """Minutes to a phrase. An elapsed window is said plainly, never as 0분."""
    if v is None or v != v:
        return NO_WINDOW_LABEL
    if v <= 0:
        return "이미 경과"
    return f"{int(round(v))}분"


def _is_elapsed(v) -> bool:
    return v is not None and v == v and v <= 0


def _rows(points: list[dict]) -> list[dict]:
    out = []
    for p in points:
        out.append({
            "label": p.get("label", "-"),
            "remaining": _fmt_remaining(p.get("closing_window_min")),
            "elapsed": _is_elapsed(p.get("closing_window_min")),
            "note": (p.get("reason_ko") if p.get("unreachable")
                     else p.get("route_note")) or "대피 경로 확인 필요",
            "unreachable": bool(p.get("unreachable")),
        })
    out.sort(key=lambda r: (not r["elapsed"], r["unreachable"]))
    return out


# -- plain text --------------------------------------------------------------


def _text_body(role: str, village: str, rows: list[dict], *, refuge: str | None,
               n_points: int, n_unreachable: int, generated_at: str,
               scope_lines: list[str], banner: str | None) -> str:
    L: list[str] = []
    if banner:
        L += [banner, ""]
    L.append(f"■ {village} — 산불 대피 안내")
    L.append("")
    if role == "가족":
        L.append(f"{village} 일대에 구조·안내가 필요한 지점이 "
                 f"{n_points}곳 확인되었습니다.")
        if n_unreachable:
            L.append(f"이 가운데 {n_unreachable}곳은 예산 시간 안에 안전한 "
                     f"도보 대피로가 없습니다.")
        if refuge:
            L.append(f"대피처는 {refuge}입니다.")
        L.append("")
        L.append("안전한 곳에서 대기하시고, 무리한 이동은 삼가 주십시오.")
    else:
        L.append(f"방문 대상 {n_points}곳입니다. "
                 f"도보 대피 불가 {n_unreachable}곳을 포함합니다.")
        elapsed = [r for r in rows if r["elapsed"]]
        if elapsed:
            L.append(f"⚠ 이미 진입 시한이 지난 곳이 {len(elapsed)}곳 있습니다.")
        L.append("")
    L.append("── 지점 목록 ──────────────────────────────")
    for i, r in enumerate(rows, start=1):
        mark = "  [시한 경과]" if r["elapsed"] else ""
        kind = "도보 대피 불가" if r["unreachable"] else "안내"
        L.append(f"{i:2d}. {r['label']}")
        L.append(f"    남은 시간 {r['remaining']}{mark} · {kind}")
        L.append(f"    {r['note']}")
    L.append("───────────────────────────────────────────")
    L.append("")
    if any(r["remaining"] == NO_WINDOW_LABEL for r in rows):
        L.append(f"※ 「{NO_WINDOW_LABEL}」는 예측 {HORIZON_H}시간 안에 해당 "
                 f"지점이 통행 불가 확률에 이르지 않는다는 뜻이며, 알 수 없다는 "
                 f"뜻이 아닙니다.")
        L.append("")
    L += scope_lines
    L.append("")
    for line in FOOTER_LINES:
        L.append(line)
    L.append(COVERAGE_CAVEAT_KO)
    L.append("")
    L.append(f"생성 {generated_at} · WildfireGuardian")
    return "\n".join(L)


# -- HTML, inline styles only (Gmail strips <style>) -------------------------

_TD = ("padding:6px 8px;border:1px solid #000;font-size:14px;"
       "vertical-align:top;color:#000;")
_TH = ("padding:6px 8px;border:1px solid #000;font-size:13px;font-weight:bold;"
       "background:#dddddd;text-align:left;color:#000;")


def _html_body(role: str, village: str, rows: list[dict], *,
               refuge: str | None, n_points: int, n_unreachable: int,
               generated_at: str, scope_lines: list[str],
               banner: str | None) -> str:
    e = _html.escape
    parts: list[str] = [
        '<div style="margin:0;padding:16px;background:#ffffff;color:#000000;'
        'font-family:\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;'
        'font-size:15px;line-height:1.5;">',
        '<div style="max-width:640px;margin:0 auto;">',
    ]
    if banner:
        parts.append(
            '<div style="border:2px solid #000;padding:8px 10px;margin:0 0 12px 0;'
            f'font-weight:bold;font-size:14px;">※ {e(banner)}</div>')
    parts.append(
        f'<h1 style="margin:0 0 4px 0;font-size:24px;line-height:1.25;">'
        f'{e(village)} 산불 대피 안내</h1>')
    parts.append(
        f'<div style="font-size:15px;font-weight:bold;margin:0 0 12px 0;">'
        f'안내 대상 {n_points}곳 · 도보 대피 불가 {n_unreachable}곳</div>')

    if role == "가족":
        lead = (f"{e(village)} 일대에 구조·안내가 필요한 지점이 "
                f"<b>{n_points}곳</b> 확인되었습니다.")
        if n_unreachable:
            lead += (f" 이 가운데 <b>{n_unreachable}곳</b>은 예산 시간 안에 "
                     f"안전한 도보 대피로가 없습니다.")
        if refuge:
            lead += f" 대피처는 <b>{e(refuge)}</b>입니다."
        lead += " 안전한 곳에서 대기하시고, 무리한 이동은 삼가 주십시오."
    else:
        n_elapsed = sum(1 for r in rows if r["elapsed"])
        lead = (f"방문 대상 <b>{n_points}곳</b>입니다. 도보 대피 불가 "
                f"<b>{n_unreachable}곳</b>을 포함합니다.")
        if n_elapsed:
            lead += (f' <span style="font-weight:bold;">⚠ 이미 진입 시한이 '
                     f'지난 곳이 {n_elapsed}곳 있습니다.</span>')
    parts.append(f'<p style="margin:0 0 14px 0;">{lead}</p>')

    parts.append(
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;border-collapse:collapse;border:1px solid #000;'
        'margin:0 0 14px 0;">')
    parts.append(
        f'<tr><th style="{_TH}width:34px;">번호</th>'
        f'<th style="{_TH}">위치</th>'
        f'<th style="{_TH}width:84px;">남은 시간</th>'
        f'<th style="{_TH}">상태 · 경로</th></tr>')
    for i, r in enumerate(rows, start=1):
        bg = "background:#eeeeee;" if r["unreachable"] else ""
        rem = e(r["remaining"])
        if r["elapsed"]:
            rem = (f'<span style="font-weight:bold;border:1px solid #000;'
                   f'padding:0 4px;">{rem}</span>')
        kind = "도보 대피 불가" if r["unreachable"] else "안내"
        parts.append(
            f'<tr style="{bg}">'
            f'<td style="{_TD}text-align:right;">{i}</td>'
            f'<td style="{_TD}">{e(r["label"])}</td>'
            f'<td style="{_TD}white-space:nowrap;font-weight:bold;">{rem}</td>'
            f'<td style="{_TD}"><b>{kind}</b><br>{e(r["note"])}</td></tr>')
    parts.append("</table>")
    if any(r["remaining"] == NO_WINDOW_LABEL for r in rows):
        parts.append(
            f'<p style="margin:0 0 12px 0;font-size:12px;">※ 「{NO_WINDOW_LABEL}」는 '
            f'예측 {HORIZON_H}시간 안에 해당 지점이 통행 불가 확률에 이르지 않는다는 '
            f'뜻이며, 알 수 없다는 뜻이 아닙니다.</p>')

    parts.append('<div style="border:1px solid #000;padding:8px 10px;'
                 'margin:0 0 12px 0;font-size:13px;">'
                 + "<br>".join(e(s) for s in scope_lines) + "</div>")
    parts.append('<div style="border-top:3px solid #000;padding-top:8px;'
                 'font-size:13px;font-weight:bold;line-height:1.45;">'
                 + "".join(f"<div>{e(line)}</div>" for line in FOOTER_LINES)
                 + f'<div style="font-weight:normal;margin-top:6px;">'
                   f'{e(COVERAGE_CAVEAT_KO)}</div>'
                 + "</div>")
    parts.append(f'<div style="margin-top:10px;font-size:12px;color:#000;">'
                 f'생성 {e(generated_at)} · WildfireGuardian</div>')
    parts += ["</div>", "</div>"]
    return "".join(parts)


def compose_family(village: str, points: list[dict], *,
                   refuge: str | None = None, generated_at: str | None = None,
                   scope_lines: list[str] | None = None,
                   banner: str | None = None) -> EmailMessageDraft:
    """Message to a family member: how many points, and where the refuge is."""
    return _compose("가족", village, points, refuge=refuge,
                    generated_at=generated_at, scope_lines=scope_lines,
                    banner=banner)


def compose_welfare(village: str, points: list[dict], *,
                    refuge: str | None = None, generated_at: str | None = None,
                    scope_lines: list[str] | None = None,
                    banner: str | None = None) -> EmailMessageDraft:
    """Message to a welfare worker: the visit list, elapsed windows flagged."""
    return _compose("복지사", village, points, refuge=refuge,
                    generated_at=generated_at, scope_lines=scope_lines,
                    banner=banner)


def _compose(role: str, village: str, points: list[dict], *,
             refuge: str | None, generated_at: str | None,
             scope_lines: list[str] | None,
             banner: str | None) -> EmailMessageDraft:
    gen = generated_at or datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    rows = _rows(points)
    n_points = len(points)
    n_unreach = sum(1 for p in points if p.get("unreachable"))
    sl = list(scope_lines or [])
    return EmailMessageDraft(
        recipient_role=role, village=village,
        subject=subject_for(village, gen),
        text_body=_text_body(role, village, rows, refuge=refuge,
                             n_points=n_points, n_unreachable=n_unreach,
                             generated_at=gen, scope_lines=sl, banner=banner),
        html_body=_html_body(role, village, rows, refuge=refuge,
                             n_points=n_points, n_unreachable=n_unreach,
                             generated_at=gen, scope_lines=sl, banner=banner),
        n_points=n_points, n_unreachable=n_unreach, generated_at=gen)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


@dataclass
class SendResult:
    """What happened, in terms safe to write into an artifact."""

    sent: bool
    dry_run: bool
    recipient_masked: str
    subject: str
    role: str
    village: str
    elapsed_s: float = 0.0
    message_id: str | None = None
    reason: str = ""
    error: str = ""
    failure_kind: str = ""
    attempted_utc: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def as_dict(self) -> dict:
        return {
            "sent": self.sent, "dry_run": self.dry_run,
            "recipient_masked": self.recipient_masked,
            "subject": self.subject, "recipient_role": self.role,
            "village": self.village,
            "attempted_utc": self.attempted_utc,
            "elapsed_s": round(self.elapsed_s, 3),
            "message_id": self.message_id,
            "reason": self.reason, "error": self.error,
            "failure_kind": self.failure_kind,
            "credentials_recorded": False,
        }


def build_mime(draft: EmailMessageDraft, to_address: str,
               from_address: str) -> EmailMessage:
    """Assemble the multipart/alternative message. No credentials involved."""
    msg = EmailMessage()
    msg["Subject"] = draft.subject
    msg["From"] = formataddr((SENDER_NAME, from_address))
    msg["To"] = to_address
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="wildfireguardian.local")
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(draft.text_body)
    msg.add_alternative(draft.html_body, subtype="html")
    return msg


def send(draft: EmailMessageDraft, to_address: str, approval_token: str, *,
         dry_run: bool = True, env: dict[str, str] | None = None,
         smtp_factory=None) -> SendResult:
    """Send one message. **Requires** an explicit approval token.

    ``approval_token`` is mandatory and positional: ``send(draft, addr)`` is a
    ``TypeError`` at the call site, and a blank or placeholder token raises
    :class:`ApprovalRequired`. Both fire before any SMTP object exists.

    ``dry_run`` defaults to **True**. A caller that wants to transmit has to say
    so, in the same call, on purpose.

    ``to_address`` must equal ``DEMO_RECIPIENT``. Anything else raises
    :class:`RecipientNotAllowed` before a connection is opened — there is no
    unsend for an evacuation notice delivered to a stranger.

    The app password is read from the environment inside this function and is
    never returned, logged, or placed in any exception message.
    """
    _check_token(approval_token)

    src = env or os.environ
    allowed = allowed_recipient(src)
    target = (to_address or "").strip()
    if not allowed:
        raise RecipientNotAllowed(
            f"{ENV_RECIPIENT} is not set, so there is no approved recipient to "
            "check against. Refusing to send.")
    if target.lower() != allowed.lower():
        raise RecipientNotAllowed(
            f"refusing to send to {mask_address(target)}: the only approved "
            f"recipient is {ENV_RECIPIENT} ({mask_address(allowed)}). This "
            "channel is restricted to a single demonstration mailbox.")

    masked = mask_address(target)
    if dry_run:
        return SendResult(
            sent=False, dry_run=True, recipient_masked=masked,
            subject=draft.subject, role=draft.recipient_role,
            village=draft.village,
            reason="DRY_RUN: composed and validated; nothing was transmitted")

    if not credentials_present(src):
        return SendResult(
            sent=False, dry_run=False, recipient_masked=masked,
            subject=draft.subject, role=draft.recipient_role,
            village=draft.village,
            reason=f"{ENV_APP_PASSWORD} absent; nothing was transmitted")

    sender = gmail_address(src)
    password = (src.get(ENV_APP_PASSWORD) or "").strip()
    msg = build_mime(draft, target, sender)

    t0 = time.monotonic()
    try:
        if smtp_factory is not None:
            client = smtp_factory()
        else:
            client = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT,
                                      context=ssl.create_default_context(),
                                      timeout=30)
        with client as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
    except Exception as exc:                                  # noqa: BLE001
        # The password can appear in an SMTP library's exception text. Report
        # the TYPE and a scrubbed message, never the raw string.
        text = str(exc).replace(password, "<REDACTED>") if password else str(exc)
        return SendResult(
            sent=False, dry_run=False, recipient_masked=masked,
            subject=draft.subject, role=draft.recipient_role,
            village=draft.village, elapsed_s=time.monotonic() - t0,
            error=f"{type(exc).__name__}: {text[:300]}",
            failure_kind=_classify_smtp_error(exc),
            reason="SMTP failure; nothing confirmed delivered")
    finally:
        del password

    return SendResult(
        sent=True, dry_run=False, recipient_masked=masked,
        subject=draft.subject, role=draft.recipient_role,
        village=draft.village, elapsed_s=time.monotonic() - t0,
        message_id=msg["Message-ID"], reason="delivered to the SMTP server")


__all__ = [
    "ApprovalRequired", "COVERAGE_CAVEAT_KO", "CredentialsMissing",
    "EmailMessageDraft", "ENV_ADDRESS", "ENV_APP_PASSWORD", "ENV_RECIPIENT",
    "RecipientNotAllowed", "SendResult", "allowed_recipient", "build_mime",
    "compose_family", "compose_welfare", "credentials_present",
    "gmail_address", "HORIZON_H", "mask_address", "NO_WINDOW_LABEL",
    "send", "subject_for",
]
