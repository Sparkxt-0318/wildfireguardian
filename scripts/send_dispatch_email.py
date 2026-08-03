#!/usr/bin/env python
"""Send one village's dispatch notice by email — behind an explicit approval gate.

Round-3 PHASE 7.

    ⚠ THIS SCRIPT CAN ACTUALLY SEND. Everything else in the delivery layer
      writes files. This does not, and that is why the gate is a gate rather
      than a flag.

THREE INDEPENDENT LOCKS, ALL OF WHICH MUST BE OPEN
--------------------------------------------------
1. ``--confirm-send`` on the command line. Without it the run is a DRY RUN and
   the SMTP layer is never reached.
2. A **typed confirmation word** at the prompt. Not ``y/N`` — a single
   keystroke is too easy to give by reflex, so the operator must type the whole
   word ``발송확인`` (or ``SEND``). Anything else aborts.
3. ``delivery.email.send`` itself requires a positional ``approval_token`` and
   refuses any recipient other than ``DEMO_RECIPIENT``.

There is deliberately **no flag that skips step 2**. ``tests/test_email_delivery.py``
asserts that against the call AST: no ``send(...)`` call in this file may be
reached without ``confirm_or_abort`` having run first.

WHAT IT SENDS
-------------
The village's own dispatch list, read from a PHASE-6 run directory
(``outputs/live/.../MANIFEST.json``) so the email says exactly what the A4 sheet
says. Two audiences, composed separately: 가족 and 복지사.

WHAT IS RECORDED
----------------
``email_sent.json`` in the run directory: masked recipient, subject, timing,
success. **Never the app password**, and never a full address.

Run:
    python scripts/send_dispatch_email.py --list
    python scripts/send_dispatch_email.py                     # DRY RUN
    python scripts/send_dispatch_email.py --confirm-send      # asks, then sends
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.delivery import email as em  # noqa: E402

from run_live_detection import load_dotenv  # noqa: E402

#: The word an operator must type in full. A single letter is too easy to give
#: by reflex, and this action cannot be undone.
CONFIRM_WORDS: tuple[str, ...] = ("발송확인", "SEND")

EXIT_ABORTED = 3
EXIT_NO_RUN = 2


def find_latest_run(root: Path) -> Path | None:
    runs = [p for p in root.glob("*/*/MANIFEST.json")] + \
           [p for p in root.glob("*/MANIFEST.json")]
    if not runs:
        return None
    return sorted(runs, key=lambda p: p.stat().st_mtime)[-1].parent


def load_village(run_dir: Path, village_index: int) -> tuple[dict, dict]:
    man = json.loads((run_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    villages = man.get("villages") or []
    if not villages:
        raise SystemExit(f"no villages in {run_dir}/MANIFEST.json")
    if not (1 <= village_index <= len(villages)):
        raise SystemExit(f"--village must be 1..{len(villages)}")
    return man, villages[village_index - 1]


def points_for(run_dir: Path, village: dict) -> list[dict]:
    """The village's points, read STRUCTURALLY from the run manifest.

    An earlier version scraped the A4 sheet's HTML table. It looked reasonable
    and was wrong: the unreachable-row detector tested the row's inner HTML for
    the ``unreach`` class, which lives in the ``<tr>`` tag it had already
    stripped, so every unreachable point was parsed as a dispatch point and its
    confirmation-checkbox column became its route note. A rendering is not a
    data source. `live.pipeline.deliver` now writes the points into
    ``MANIFEST.json`` and this reads them.
    """
    pts = village.get("points")
    if pts is None:
        raise SystemExit(
            f"{run_dir/'MANIFEST.json'} has no per-village 'points' — it was "
            "written before PHASE 7. Regenerate the run:\n"
            "  python scripts/run_live_detection.py --replay")
    return list(pts)


def show(draft: em.EmailMessageDraft, recipient: str, *, dry_run: bool) -> None:
    bar = "=" * 74
    print(bar)
    print(f"  {'DRY RUN — 발송하지 않습니다' if dry_run else '실제 발송 준비'}")
    print(bar)
    print(f"  받는 사람 : {em.mask_address(recipient)}   (전체 주소: {recipient})")
    print(f"  보내는 이 : {em.gmail_address()}")
    print(f"  제목      : {draft.subject}")
    print(f"  수신 유형 : {draft.recipient_role}")
    print(f"  마을      : {draft.village}  "
          f"(지점 {draft.n_points}곳 · 도보 대피 불가 {draft.n_unreachable}곳)")
    print(bar)
    print(draft.text_body)
    print(bar)


def confirm_or_abort(recipient: str, n_messages: int) -> str:
    """Block until a human types the confirmation word in full.

    Returns the approval token. Raises SystemExit on anything else. There is no
    parameter that skips this, and no caller may construct the token itself.
    """
    print()
    print("  ⚠ 이 작업은 되돌릴 수 없습니다. 발송된 메일은 회수할 수 없습니다.")
    print(f"  ⚠ 수신자: {recipient}")
    print(f"  ⚠ 발송 건수: {n_messages}건")
    print()
    print(f"  발송하려면 다음 단어를 그대로 입력하십시오: "
          f"{' 또는 '.join(CONFIRM_WORDS)}")
    print("  (그 외의 입력은 모두 취소로 처리됩니다)")
    try:
        typed = input("  입력> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  입력이 없어 취소했습니다. 발송하지 않았습니다.", file=sys.stderr)
        raise SystemExit(EXIT_ABORTED) from None
    if typed not in CONFIRM_WORDS:
        print(f"  '{typed}' 은(는) 확인 단어가 아닙니다. 취소했습니다. "
              f"발송하지 않았습니다.", file=sys.stderr)
        raise SystemExit(EXIT_ABORTED)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    print("  확인되었습니다. 발송합니다.\n")
    return f"operator-confirmed-{stamp}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", default=None,
                    help="a PHASE-6 run directory (default: the most recent)")
    ap.add_argument("--village", type=int, default=1,
                    help="1-based index into the run's village list")
    ap.add_argument("--role", choices=["가족", "복지사", "both"], default="both")
    ap.add_argument("--confirm-send", action="store_true",
                    help="arm the send path. Without this the run is a DRY RUN "
                         "and SMTP is never reached. Even with it, the typed "
                         "confirmation is still required.")
    ap.add_argument("--list", action="store_true",
                    help="list the run's villages and exit")
    args = ap.parse_args()

    load_dotenv(REPO / ".env")

    root = REPO / "outputs" / "live"
    run_dir = Path(args.run_dir) if args.run_dir else find_latest_run(root)
    if run_dir is None or not (run_dir / "MANIFEST.json").exists():
        print(f"STOP: no PHASE-6 run found under {root}. Generate one with:\n"
              "  python scripts/run_live_detection.py --replay",
              file=sys.stderr)
        return EXIT_NO_RUN

    man = json.loads((run_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    if args.list:
        print(f"run: {run_dir.relative_to(REPO)}")
        for i, v in enumerate(man["villages"], start=1):
            print(f"  {i:2d}. {v['name']:28s} 지점 {v['n_points']:2d} "
                  f"(안내 {v['n_dispatch']:2d} / 도보 불가 {v['n_unreachable']:2d})")
        return 0

    _man, village = load_village(run_dir, args.village)
    pts = points_for(run_dir, village)
    scope = (man.get("scope") or {})
    scope_lines = [ln for ln in (scope.get("detection_line_ko"),
                                 scope.get("weather_line_ko")) if ln]
    banner = scope.get("mode_banner_ko")
    refuge = village.get("refuge_used_in_messages")

    roles = (["가족", "복지사"] if args.role == "both" else [args.role])
    drafts = []
    for role in roles:
        fn = em.compose_family if role == "가족" else em.compose_welfare
        drafts.append(fn(village["name"], pts, refuge=refuge,
                         scope_lines=scope_lines, banner=banner))

    recipient = em.allowed_recipient()
    creds = em.credentials_present()
    if not recipient:
        print(f"STOP: {em.ENV_RECIPIENT} is not set in .env. There is no "
              "approved recipient, so nothing can be sent.", file=sys.stderr)
        return EXIT_NO_RUN

    # ---- 1. show what would be sent --------------------------------------
    for d in drafts:
        show(d, recipient, dry_run=not (args.confirm_send and creds))

    dry_run = True
    token = "dry-run-no-approval-needed"
    notes: list[str] = []

    if not creds:
        notes.append(
            f"{em.ENV_APP_PASSWORD} absent — DRY_RUN enforced regardless of "
            "--confirm-send. Nothing was transmitted.")
        print(f"  ⚠ {em.ENV_APP_PASSWORD} 없음 → DRY_RUN 유지. 발송하지 않습니다.")
    elif not args.confirm_send:
        notes.append("--confirm-send not given; DRY RUN.")
        print("  DRY RUN 입니다. 실제로 보내려면 --confirm-send 를 붙이십시오.")
    else:
        # Reachability is checked BEFORE the operator is asked to confirm.
        # Asking a person to authorise an irreversible action and then failing
        # on a blocked port wastes the one thing the gate is protecting.
        ok, why = em.smtp_reachable()
        if not ok:
            notes.append(f"SMTP unreachable — {why} DRY_RUN enforced.")
            print(f"  ⚠ {why}")
            print("     확인 절차를 진행하지 않고 DRY_RUN 으로 유지합니다.")
        else:
            # ---- 2 + 3. confirm the recipient, then require the typed word --
            token = confirm_or_abort(recipient, len(drafts))
            dry_run = False

    # ---- send (or not) ----------------------------------------------------
    t0 = time.monotonic()
    results = [em.send(d, recipient, token, dry_run=dry_run) for d in drafts]
    total_s = time.monotonic() - t0

    record = {
        "schema_version": 1,
        "channel": "email",
        "run_dir": str(run_dir.relative_to(REPO)),
        "village": village["name"],
        "village_index": args.village,
        "n_points": village["n_points"],
        "n_unreachable": village["n_unreachable"],
        "recipient_masked": em.mask_address(recipient),
        "recipient_is_demo_recipient_only": True,
        "sender_masked": em.mask_address(em.gmail_address()),
        "dry_run": dry_run,
        "confirm_send_flag": bool(args.confirm_send),
        "typed_confirmation_required": True,
        "credentials_present": creds,
        "app_password_recorded": False,
        "recorded_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_elapsed_s": round(total_s, 3),
        "messages": [r.as_dict() for r in results],
        "n_sent": sum(1 for r in results if r.sent),
        "all_sent": all(r.sent for r in results) if not dry_run else False,
        "scope": scope,
        "notes": notes,
    }
    out = run_dir / "email_sent.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    print("=" * 74)
    for r in results:
        state = ("발송됨" if r.sent else
                 "DRY RUN — 발송하지 않음" if r.dry_run else "실패")
        print(f"  [{r.role}] {state}  → {r.recipient_masked}  "
              f"({r.elapsed_s:.2f}s)" + (f"  {r.error}" if r.error else ""))
    print(f"  전체 소요 {total_s:.2f}s · 기록 {out.relative_to(REPO)}")
    print("=" * 74)
    return 0 if (dry_run or all(r.sent for r in results)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
