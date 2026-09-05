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

Sixteen files. `make finals-bundle` exits 0 on a tree that has not changed, and
`tests/test_finals_bundle.py` (7 tests) re-derives the same hashes independently of
the builder's own report, asserts that the manifest covers exactly the builder's
plan, that the four screens and at least one font are in it, that the recipe is ten
numbered steps that still say to turn Wi-Fi off, and that two manifests of the same
tree are equal.

## The payload is generated, not committed — and why

`release/kcf-finals-2026/web/`, `CITATION.cff` and `LICENSE` inside the bundle are
git-ignored. A clean clone therefore holds only `README_KO.md` and `MANIFEST.json`
until someone runs `make finals-bundle`.

Two reasons, both of them this repository's own rules:

1. **CHARTER §3.2.** A committed copy of `web/finals.html` (2.1 MB, rebuilt whenever
   the screen changes) is a second place for the same bytes to live, and the second
   place is the one that goes stale. The manifest carries the same guarantee without
   the copy: if the tree moves and the manifest does not, the test fails.
2. **The forbidden-string scan.** `scripts/check_forbidden.py` reads retired figures
   out of authored prose, and `docs/forbidden_check_scope.md` records exactly which
   files are records rather than claims. A duplicate of every screen would put a
   duplicate of every retired figure into that scan and would have to be argued back
   out of it, one file at a time, for no gain.

The cost is stated plainly in `README_KO.md`: the folder is not complete until the
command has been run once.

## What this does NOT show

- **That the screens work on the booth laptop.** Nothing here opens a browser. The
  bundle is assembled and hashed; whether `file://` renders it on the judged machine
  with Wi-Fi off is R12 / **NH-014**, and it needs the author and the actual laptop.
- **That the run recipe is right.** The ten steps are written from
  `docs/FINALS_DEMO.md` and the screen's own key bindings, not from a rehearsal. The
  booth procedure with the fallbacks — two USB copies, what to do if the laptop dies
  — is `docs/auto/finals/BOOTH_SETUP.md`, which does not exist yet (WFG-037).
- **That the bundle is complete for the finals.** v1 has no printables. The A4
  evidence sheet, the reconciliation sheet, the differentiation panel, the booth
  checklist and the dispatch-sheet sample are R7 / WFG-007, and v2 of this row
  (due 09-14) is the rebuild that carries them.
- **A DOI.** `CITATION.cff` carries no `doi:` and no `date-released:` because no
  release has been tagged and no DOI minted. Both are author actions from a browser
  session after the finals (WFG-031); a plausible-looking release date would be a
  fabricated figure.
- **That a corrupted USB is recoverable.** `make finals-bundle` says *that* a file
  differs, not how to get it back. The recovery is the second stick, which is why
  `README_KO.md` step 9 names it.
