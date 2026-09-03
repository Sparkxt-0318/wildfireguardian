# The paper — how it is written and built

Target: one English manuscript, under 20 pages including the title page and
references, publication-ready in tone and figures, written alongside the code by
the `wfg-autoloop-paper` routine (docs/auto/CHARTER.md §12) and rebuilt every
time the code moves. Author: **Siyeong Park (박시영)**.

| file | role |
|---|---|
| `manuscript.md` | the single source of truth; Markdown subset (see below) |
| `references.bib` | every citation, verified by opening the URL; unverified ones are not allowed in the manuscript |
| `figures/F*.png` | built by `make_figures.py` from committed artifacts only; never hand-edited |
| `style.py` | the one figure style (fonts, palette, sizes); every figure imports it |
| `make_figures.py` | regenerates every figure deterministically |
| `build_docx.py` | Markdown → `WildfireGuardian_Park_2026.docx` (python-docx; title page, numbered figures/tables, references) |
| `check_paper.py` | the paper's own gate: length budget, figure/reference integrity, gap ledger, registry-anchored numbers |
| `GAPS.md` | every `[GAP: …]` marker in the manuscript, with what closes it and when (after the sprint if needed) |
| `STATE.json` | the commit the manuscript last incorporated |

## Markdown subset `build_docx.py` understands

`# Title` (once) · `## Section` · `### Subsection` · paragraphs · `- bullets` ·
`1. numbered` · `**bold**` / `*italic*` / `` `code` `` · figures as
`![Caption text](figures/F1_system.png)` on their own line · tables in pipe
syntax with a preceding line `Table N. Caption` · citations as `[@key]` or
`[@key1; @key2]` (numbered in order of first appearance; the References section
is generated from `references.bib`) · `[GAP: what is missing]` markers, rendered
in red and mirrored in `GAPS.md`.

## Rules (from docs/auto/CHARTER.md §3, §9, §12)

- Every number comes from `docs/NUMBERS.json` or a committed artifact, and the
  registry-anchored collision gate runs over `manuscript.md` like any other
  prose. Withdrawn claims stay withdrawn.
- Figures are drawn from artifacts by `make_figures.py`; if the artifact is
  missing the figure is not drawn and the manuscript says `[GAP]`.
- The manuscript is a draft the student owns: `AUTHORSHIP.md` records that the
  loop drafted it; the abstract and any ISEF text are rewritten by the student
  before submission; nothing is submitted anywhere before the December ceremony.
- Length budget: 7,000 words of body text (≈ 16 pages at this style) plus
  references and figures; `check_paper.py` fails above 7,500.
