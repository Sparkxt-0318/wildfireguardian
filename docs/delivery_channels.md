# Delivery channels — status, and what each one can actually do

Round-3 PHASE 7. Written 2026-08-03.

`src/wildfireguardian/delivery/` · `scripts/send_dispatch_email.py` ·
`tests/test_email_delivery.py` (47 tests)

---

## 0. The safety statement — use this wording

The project used to say **"SMS 전달은 모사이며 실제 발송하지 않습니다"** (delivery
is simulated; nothing is ever sent). That was accurate while every channel wrote
files. It stopped being accurate when the email channel landed, and repeating it
would understate what the system does — which is its own kind of inaccuracy.

> **전달 문구는 자동으로 발송되지 않으며, 승인 권한을 가진 사람이 명시적으로
> 확인한 뒤에만 발송됩니다. 발송 함수는 승인 토큰 없이 호출될 수 없습니다.**
>
> Delivery text is never transmitted automatically. It is sent only after a
> person with approval authority has explicitly confirmed, and the send function
> cannot be called without an approval token.

Use that sentence wherever the old one appeared. It is true of **every** channel
below, including the ones that cannot currently transmit at all.

---

## 1. The four channels

| channel | module | audience | can it transmit? | state |
|---|---|---|---|---|
| A4 sheet | `printable.py` | 이장 | n/a — paper | **primary**, unchanged |
| 마을방송 | `broadcast.py` | village PA announcer | n/a — read aloud | unchanged |
| SMS | `sms.py` | 가족 · 복지사 | **no — DEMO_MODE** | blocked, see §3 |
| **email** | `email.py` | 가족 · 복지사 | **yes, after approval** | **PHASE 7, live** |

The A4 sheet remains the most important channel: the 2025 Yeongnam survey
(n = 300) put emergency-SMS reception in Yeongdeok at 48 %, and paper needs no
charge, no coverage, and no small-screen eyesight. Email does not displace it.

---

## 2. Email — the channel that can actually send

### Why email is a legitimate substitute, not a workaround

The two audiences SMS was written for are a **family member** and a **복지사**.
Both read email. Nothing about the message content assumes a phone: the drafts
carry place names, remaining time and a route note, and no coordinates. So the
substitution changes the transport, not the claim.

### Three independent locks

A send happens only when all three are open:

1. **`--confirm-send`** on the command line. Without it the run is a DRY RUN and
   the SMTP layer is never reached.
2. **A typed confirmation word** — `발송확인` or `SEND`, in full. Not `y/N`: a
   single keystroke is too easy to give by reflex, and an evacuation notice
   cannot be recalled. Anything else aborts with exit 3.
3. **`email.send`'s own gate** — a positional, mandatory `approval_token`, and a
   recipient check against `DEMO_RECIPIENT`.

There is deliberately **no flag that skips step 2**, and that is enforced rather
than documented: `tests/test_email_delivery.py` parses the script's AST and
asserts that the single `dry_run = False` assignment sits inside a branch that
has just called `confirm_or_abort()`. A future `--yes` shortcut fails the suite.

### One recipient, enforced in code

Every send is checked against `DEMO_RECIPIENT`. Any other address raises
`RecipientNotAllowed` **before a connection is opened** — and the exception text
prints neither the attempted address nor the allowed one, so the error cannot be
used to discover the mailbox. Case-insensitive, because a capitalised address is
the same mailbox.

### The app password

Read from `GMAIL_APP_PASSWORD` in the git-ignored `.env`, used once inside
`send`, and `del`'d in a `finally`. It is **never** logged, returned, written to
an artifact, or left in an exception message — an SMTP `535` reply can quote the
credential it rejected, so the failure path scrubs it and substitutes
`<REDACTED>`. A test asserts exactly that by raising an error containing the
password and checking it does not survive.

### Records

`email_sent.json`, written into the PHASE-6 run directory:

```json
{
  "recipient_masked": "s***0318@gmail.com",
  "dry_run": false,
  "confirm_send_flag": true,
  "typed_confirmation_required": true,
  "app_password_recorded": false,
  "total_elapsed_s": 2.42,
  "messages": [{"sent": true, "elapsed_s": 1.35, "recipient_role": "가족", …}]
}
```

Addresses are masked (`siyeong0318@gmail.com` → `s***0318@gmail.com`) — enough
to confirm the right mailbox, not enough to reconstruct it.

### HTML

Gmail strips `<style>` blocks, so **every rule is an inline `style=` attribute**.
No external stylesheet, no web font, no image, no script — the message must
render in a plain client, in monochrome, with images blocked, for someone
reading on a phone at night. Tests assert the absence of `<style>`, `@media`,
`<link>`, `<script>`, `<img>` and any `src="http…"`.

The HTML carries the same table as the A4 sheet — 번호 / 위치 / 남은 시간 /
상태·경로 — with unreachable rows shaded *and* labelled, because a village
printer is monochrome and a shade alone is not information.

Both bodies carry, without exception:

* the two fixed cautions, **imported from `printable.FOOTER_LINES`** rather than
  retyped, so the paper and the email cannot drift apart;
* the 32.6 % coverage caveat (§2-A);
* the PHASE-6 scope statement (detection is real-time, weather is not) and the
  replay banner when the run was a replay.

---

## 3. SMS — why it stays in DEMO_MODE

The Twilio **trial** account cannot verify a Korean mobile number without an
account upgrade. A trial account may only send to numbers verified in the
console, and the verification step for `+82` numbers is gated behind the paid
tier. So the SMS channel cannot deliver to the demonstration handset, and
`DEMO_MODE` stays on.

⚠ `.env` now contains `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and
`TWILIO_FROM_NUMBER`. **Their presence does not mean SMS can send.** The
credentials are real and the account restriction is what blocks delivery, so
`sms.credentials_present()` returning `True` must never be read as "SMS is
live". `DEMO_MODE` is on unless the environment variable is exactly `"0"`, and
`sms.send` still requires a positional `approval_token`.

`sms.py` is **not** deleted and its behaviour is unchanged. If the account is
upgraded later, the channel is one environment variable away from working, and
its approval gate is already the same shape as email's.

---

## 3-B. ⚠ The verification send did NOT complete — outbound SMTP is blocked

The channel is implemented, gated and exercised end to end **up to the TCP
connection**. It has **not** delivered a message, because this machine's network
blocks outbound SMTP on every port:

```
smtp.gmail.com:465   TimeoutError
smtp.gmail.com:587   TimeoutError
smtp.gmail.com:25    TimeoutError
firms.…gov:443       OPEN          ← control: HTTPS works fine
```

Tested both inside and outside the tool sandbox, with the same result, so it is
the network — not a sandbox policy and **not the credential**. Blocking
outbound 25/465/587 is standard practice on corporate, campus and most Korean
consumer ISP networks to limit spam relays.

What this means precisely:

* the app password was **never presented to Gmail**, so nothing is known about
  whether it is valid — a `TimeoutError` implies nothing about a credential;
* one real attempt was made and recorded with `failure_kind: network`
  (`outputs/live/replay/…/email_sent.json`, 30.06 s to time out);
* the script now runs `smtp_reachable()` **before** asking the operator to
  confirm, so a blocked port no longer spends the one thing the gate protects:
  a person's explicit authorisation. On an unreachable port it stays DRY RUN,
  says why, and exits 0.

**To complete the verification**, run it from a network that permits outbound
SMTP (most home connections, or a mobile hotspot):

```bash
python scripts/send_dispatch_email.py --village 1 --role 복지사 --confirm-send
```

The remaining alternative — the Gmail **API** over HTTPS 443, which this network
does allow — needs OAuth rather than an app password, and setting up OAuth
credentials is a separate piece of work that was not part of this phase.

---

## 4. A divergence this phase found and did not paper over

An origin with **no closing window** renders as **"확인 불가"** on the A4 sheet
and as **"12시간 내 미도달"** in the email. Both describe the same value, and the
email's label is the accurate one.

In the 439 series an absent window really was *unknown*. In the 459/canonical
series it is a **positive statement**: `_time_to_cutoff` walks the field's five
time slices (0…720 min) and returns infinity when the location never reaches
p ≥ 0.5 within the 12-hour horizon. Rendering that as "확인 불가" reads as a
hedge about data quality when the model is in fact making a claim.

**The A4 layer was not edited** — PHASE 7's scope explicitly excludes it, and
the committed sheets are cited. So the email says the accurate thing, the
divergence is recorded here, and correcting `printable._fmt_remaining` for the
459 path is left as a scoped follow-up. It is a wording defect, not a numeric
one: no count changes either way.

---

## 5. A second thing this phase found

The first version of `send_dispatch_email.py` read each village's points by
**scraping the A4 sheet's HTML table**. It looked reasonable and was wrong: the
unreachable-row detector tested the row's *inner* HTML for the `unreach` class,
which lives in the `<tr>` tag the regex had already stripped. Every unreachable
point was therefore parsed as a dispatch point, and its confirmation-checkbox
column (`□`) became its route note — visible in the first dry run as a point
reported with the wrong status and an empty reason.

Fixed at the source rather than in the parser: `live.pipeline.deliver` now
writes each village's points **structurally** into `MANIFEST.json`, and the
email script reads them. A rendering is not a data source.

Coordinates are deliberately excluded from that block — every operational
artifact in this project is coordinate-free by requirement.

---

## 6. Commands

```bash
python scripts/send_dispatch_email.py --list                       # villages
python scripts/send_dispatch_email.py --village 1                  # DRY RUN
python scripts/send_dispatch_email.py --village 1 --confirm-send   # asks, sends
```

| flag | |
|---|---|
| `--run-dir` | a PHASE-6 run directory (default: most recent) |
| `--village N` | 1-based index into that run's village list |
| `--role` | `가족` · `복지사` · `both` (default) |
| `--confirm-send` | arms the send path; the typed confirmation is still required |
| `--list` | show the run's villages and exit |

Exit codes: `0` success or dry run · `1` a send failed · `2` no run / no
recipient configured · `3` **operator aborted at the confirmation**.

---

## 7. Environment

| variable | purpose | required for |
|---|---|---|
| `GMAIL_ADDRESS` | sender | real send |
| `GMAIL_APP_PASSWORD` | Gmail app password (16 chars) | real send |
| `DEMO_RECIPIENT` | the **only** permitted recipient | any send |
| `TWILIO_*` | present, but SMS stays DEMO_MODE (§3) | — |

If `GMAIL_APP_PASSWORD` is absent the script **enforces DRY RUN regardless of
`--confirm-send`**, reports it, and exits 0. It does not stop and it does not
ask.
