# The finals release bundle

**Row:** WFG-036 v1 · **Readiness line:** R9 · **Written by:** the automated loop,
2026-09-05 · **Gate:** `tests/test_finals_bundle.py`, `make finals-bundle`

## What it is

`release/kcf-finals-2026/` is the folder that goes on the USB stick for the 2026
Korea Code Fair finals: the four offline screens (`finals`, `console`, `field_view`,
`refuge_placement`), the fonts and poster image they need to render without a
network, `LICENSE`, `CITATION.cff`, a ten-step Korean run recipe (`README_KO.md`),
and `MANIFEST.json`.

## Method

`scripts/build_finals_bundle.py` copies each payload file out of the repository
byte for byte, then writes the SHA-256, byte size and source path of every file into
`MANIFEST.json`. Nothing in the bundle is computed, rendered or reformatted — the
builder is a copy and a hash, so two runs on the same tree produce the same bytes.

`make finals-bundle` runs it in check mode: it re-assembles the bundle, re-derives
every hash, and exits non-zero naming any file that differs from the committed
manifest. `make finals-bundle UPDATE=1` is the deliberate rewrite, run by a lap that
has changed a payload file on purpose.

## Result

Seventeen files (sixteen until 2026-09-05, when WFG-037 added
`check_bundle_copy.py` to the payload so the laptop-has-died case can verify a stick
without this repository). `make finals-bundle` exits 0 on a tree that has not changed, and
`tests/test_finals_bundle.py` (7 tests) re-derives the same hashes independently of
the builder's own report, asserts that the manifest covers exactly the builder's
plan, that the four screens and at least one font are in it, that the recipe is ten
numbered steps that still say to turn Wi-Fi off, and that two manifests of the same
tree are equal.

## The payload is generated, not committed — and why

`release/kcf-finals-2026/web/`, `CITATION.cff` and `LICENSE` inside the bundle are
git-ignored. A clean clone therefore holds only `README_KO.md` and `MANIFEST.json`
until someone runs `make finals-bundle`.

One reason, and it is **CHARTER §3.2**: a committed copy of `web/finals.html` (2.1 MB,
rebuilt whenever the screen changes) is a second place for the same bytes to live, and
the second place is the one that goes stale. One copy plus a hash instead of two copies.

`MANIFEST.json` is itself a derivative and can go stale the same way — that is not a
difference in kind, and it should not be claimed as one. The difference is what happens
when it does: a stale hash line fails
`tests/test_finals_bundle.py::test_every_hash_in_the_manifest_is_the_hash_of_the_source_file`
on the next run, while a stale 2.1 MB copy of a screen fails nothing and is read by
nobody until a judge is looking at it.

> **A reason this document used to give, and it was wrong.** The first version of this
> file, of the `.gitignore` comment beside these rules and of the lap report that shipped
> them claimed a second reason: that a committed copy of the screens would drop a
> duplicate of every retired figure into `scripts/check_forbidden.py`'s prose scope. The
> lap's independent reviewer checked it and it is false —
> `check_forbidden.py`'s `is_authored_prose()` is `rel.lower().endswith(".md")`, so
> retired-figure rules never reach an `.html` file at all, and `web/finals.html` is
> already tracked and already green. A copy would have added exactly zero findings. It
> was a claim about this repository's own gate, asserted without running the gate, in a
> lap that had just run it. It is recorded here rather than deleted, because that is what
> this repository does with a withdrawn reason.

The cost of the choice is stated plainly in `README_KO.md`: the folder is not complete
until the command has been run once.

## What this does NOT show

- **That the screens work on the booth laptop.** Nothing here opens a browser. The
  bundle is assembled and hashed; whether `file://` renders it on the judged machine
  with Wi-Fi off is R12 / **NH-014**, and it needs the author and the actual laptop.
- **That the run recipe is right.** The ten steps are written from
  `docs/FINALS_DEMO.md` and the screen's own key bindings, not from a rehearsal. The
  booth procedure with the fallbacks — two USB copies, what to do if the laptop dies
  — is `docs/auto/finals/BOOTH_SETUP.md`, written 2026-09-05 (WFG-037). It is still
  not a rehearsal: NH-014 / R12 is the author reading it on the actual laptop.
- **That the bundle is complete for the finals.** It now carries the booth kit —
  `printables/WFG_printables_<stamp>.pdf` and its manifest, resolved from the newest
  tracked stamp rather than named by a literal (WFG-151) — so the evidence sheet, the
  reconciliation sheet and the booth checklist are on the stick. ⚠ 〔updated
  2026-09-07T0630Z〕 this sentence said **two** of R7's five were still not on the
  stick. It is now **one**: WFG-026 shipped the related-work and SFTD059T
  differentiation panel (`docs/auto/finals/RELATED_WORK_PANEL.md`, summarising the
  16-entry survey in `docs/related_work.md`), it is `SOURCES` entry six of the kit
  rebuilt at `20260907T0705Z`, and the bundle carries that stamp. **Four of R7's five
  are on the stick; the dispatch-sheet sample is the one that is not.**
  ⚠ **That second reason was wrong here for one commit and the correction is worth
  keeping.** This bullet said 「the 29 dispatch sheets are already committed PDFs that <!-- forbidden-ok: wc006-dispatch-committed-pdfs, wc006-29-dispatch-sheets -->
  print directly」, which is what R7's line and `tests/test_printables.py` `R7_ITEMS`
  both say. The tree says otherwise: `outputs/dispatch/20260801T163042Z/` holds **33**
  clusters, and while the HTML, SMS drafts and broadcast scripts are committed for all
  33, only the **three largest clusters' PDFs** are — `outputs/dispatch/README.md`
  states it plainly, because 33 Korean-font-subset PDFs come to 6.7 MB of regenerable
  output, rebuilt with `python scripts/generate_dispatch_outputs.py`. So the exclusion
  is sound but its stated reason was not: the sheets are **regenerable from a committed
  artifact**, not already-printed PDFs waiting in the folder. Neither 「29」 nor
  「committed」 traced to anything; 「29」 came from an aspiration in
  `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md`. Found by WFG-151's independent
  reviewer, which checked the reason against the tree instead of against the loop's
  own earlier prose. The upstream copies in R7's line and in the printables manifest's
  `what_this_does_not_show` carry the same error and are **WFG-153**.
  〔기록 · 2026-09-07 이전〕 this bullet read 「v1 has no printables. The A4 evidence
  sheet, the reconciliation sheet, the differentiation panel, the booth checklist and
  the dispatch-sheet sample are R7 / WFG-007, and v2 of this row (due 09-14) is the
  rebuild that carries them」. **That sentence stayed true the whole time** — the kit
  was built into the repository at `3e92b69` on 2026-09-06T0651Z, and the bundle
  still did not contain it a day later. Nothing here needed withdrawing; the bundle
  needed rebuilding, which is why WFG-151 is a defect in `PAYLOAD` and in the test
  that never read R9, and not a prose correction.
- **A DOI.** `CITATION.cff` carries no `doi:` and no `date-released:` because no
  release has been tagged and no DOI minted. Both are author actions from a browser
  session after the finals (WFG-031); a plausible-looking release date would be a
  fabricated figure.
- **That a corrupted USB is detected at all — withdrawn 2026-09-05 (WFG-037).** What
  stood here read: 「`make finals-bundle` says *that* a file differs, not how to get it
  back」. The first half is false for a USB copy, and the builder's own docstring and
  the `finals-bundle` comment in the Makefile said the same thing. `assemble()` copies
  every payload file out of the repository over the top of the bundle **before**
  anything is hashed, so a file that went bad on the stick is repaired, not reported.
  Measured by appending seven bytes to `release/kcf-finals-2026/web/finals.html` and
  running the builder: the file was overwritten and the run printed `OK`.
  `scripts/check_bundle_copy.py` is the check that was missing — it reads a folder and
  never writes to it, imports nothing outside the standard library, travels inside the
  bundle, and is graded against a flipped byte, a truncation, a deletion and a stray
  file (`tests/test_check_bundle_copy.py`). The recovery for a bad file is still the
  second stick, which is why `README_KO.md` names it.
- **That the folder on disk holds only what the manifest lists.** `make finals-bundle`
  compares two manifests and never scans the folder, so a file left behind by an
  earlier run stays in `release/kcf-finals-2026/` and rides onto the USB stick while
  the builder reports `byte-identically`. Found 2026-09-05 by running the new checker
  immediately after a green builder run; filed as **WFG-108**. Until the builder prunes,
  `docs/auto/finals/BOOTH_SETUP.md` §2 makes the copy check a step, not an option.
