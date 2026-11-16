# Bundled font

`NotoSansKR-subset-400.woff2` and `NotoSansKR-subset-700.woff2` are subsets of **Noto Sans KR** (Google), licensed
under the SIL Open Font License 1.1 (`OFL.txt`). Source: npm package `@fontsource/noto-sans-kr@5.3.1`. Its
unicode-range parts were merged and subset with fontTools 4.68 to:

- printable ASCII;
- the 2,350 Hangul syllables of KS X 1001;
- every character in this package's `src/`, `fixtures/`, `docs/` and `qa/planner-4169ccc/inputs/`;
- common symbols (· — → ≠ × ※ □ ○ etc.).

They are embedded in `viewer.html` as data URIs and linked from the static example pages, so print layout does not
depend on the fonts installed on a machine. Any Hangul syllable outside the subset falls back per glyph to a
system Korean font (Malgun Gothic, Apple SD Gothic Neo, …). This is a modified version under OFL §3, and the
Noto declares no Reserved Font Name; the subset is still renamed "KCF Noto Sans KR Subset" (name table) so it is not mistaken for the original.
