#!/usr/bin/env python
"""Extract the 2025 영남 산불 survivor-survey figures from the source PDF.

Backlog WFG-020. The point of this script is that the numbers this project
quotes from a third-party report are READ OUT OF THAT REPORT by a program,
not typed in by hand from someone's notes. The distinction matters here more
than usual: the figures reached this repository through a scratchpad text
extraction that no longer exists, so until this lap nothing tied them to the
document they claim to come from. A sha256 beside a hand-typed number
authenticates the PDF, not the transcription.

So:

* the PDF is identified by sha256 before a single number is read (``--pdf``);
  a digest mismatch is a hard failure, never a warning;
* every required figure is parsed out of the report's own answer tables;
* each parsed figure is checked against the value this repository claims
  (``PINS``) and against its own table arithmetic (count / base == percent);
* the script refuses to write anything if any of those disagree.

The output ``data/processed/evidence/greenpeace_2026_survey.json`` is a
TRANSCRIPTION of someone else's measurement. It is deliberately NOT registered
in ``docs/NUMBERS.json``: that registry means "this project derived this number
from its own committed artifact", and these numbers are neither derived by this
project nor reproducible by re-running its pipeline. They are evidence about
the world, carried with their provenance. See docs/evidence/greenpeace_2026_survey.md.

The PDF itself is not committed. ``data/raw/**`` is git-ignored (it is a 3.4 MB
third-party report), so on a fresh clone this script cannot run and the tests
that need it skip with that reason; the committed JSON is what travels.

Usage:

    pip install -e ".[evidence]"      # pypdf, needed only to re-extract
    python scripts/extract_survey_evidence.py
    python scripts/extract_survey_evidence.py --pdf /path/to/report.pdf
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# --- the source -------------------------------------------------------------

SOURCE = {
    "title": "2025 영남 초대형 산불 피해 실태조사 최종보고서",
    "subtitle": "안동, 영덕, 의성을 중심으로",
    "publisher": "그린피스 동아시아 서울사무소 · 녹색전환연구소 · 재난피해자권리센터 '우리함께' 공동 조사",
    "published": "2026-03",
    "url": (
        "https://www.greenpeace.org/static/planet4-korea-stateless/2026/03/"
        "d2fe67f5-2025-%EC%98%81%EB%82%A8-%EC%B4%88%EB%8C%80%ED%98%95-%EC%82%B0%EB%B6%88-"
        "%EC%8B%A4%ED%83%9C%EC%A1%B0%EC%82%AC-%EC%B5%9C%EC%A2%85%EB%B3%B4%EA%B3%A0%EC%84%9C.pdf"
    ),
    "retrieved_utc": "2026-09-03T18:21Z",
    "sha256": "db15d70580e136b9a636ffbf4c84b29a53ec6d517e5c11d5b8d82a79f6653310",
    "bytes": 3406169,
    "pages": 191,
}

DEFAULT_PDF = REPO / "data" / "raw" / "evidence" / "greenpeace_2026_yeongnam_survey.pdf"
DEFAULT_OUT = REPO / "data" / "processed" / "evidence" / "greenpeace_2026_survey.json"

REGIONS = ("전체", "안동", "영덕", "의성")

#: Percent-style answer tables: id -> (column names, rows this script REQUIRES).
#: A row not required is one the PDF's own layout splits across a page break so
#: that counts and percentages are no longer interleaved (표 3-4 의성); it is
#: recorded as unparsed rather than guessed at.
TABLES = {
    "표 1-1": {
        "question": "귀하의 연령대는 다음 중 어디에 속하십니까?",
        "columns": ["40세 미만", "40-59세", "60-79세", "80세 이상"],
        "required": REGIONS,
    },
    "표 1-5": {
        "question": "재해 이전 함께 거주한 사람의 수는 몇이었습니까? (본인 제외)",
        "columns": ["0명", "1명", "2명", "3명", "4명 이상"],
        "required": REGIONS,
    },
    "표 1-6": {
        "question": "귀하는 올해 재해를 피해 살던 주거지를 떠나 대피했습니까?",
        "columns": ["그렇다", "아니다"],
        "required": REGIONS,
    },
    "표 3-1": {
        "question": "재해 당시 휴대전화로 전송되는 재난 문자를 받으셨습니까?",
        "columns": ["받았다", "받지 못했다"],
        "required": REGIONS,
    },
    "표 3-3": {
        "question": "구조되거나 대피소로 이동할 때 이용한 수단은 다음 중 무엇이었습니까?",
        "columns": ["승용차", "도보", "배", "버스", "기타"],
        "required": REGIONS,
    },
    "표 3-4": {
        "question": "차량을 이용해 대피하셨다면, 어떤 종류의 차량이었습니까?",
        "columns": ["본인의 차", "마을 주민의 차", "가족이나 친척의 차", "공공구조차량", "기타"],
        "required": ("전체", "안동", "영덕"),
    },
    "표 3-5": {
        "question": "재해 당시 생명의 위협을 느꼈습니까?",
        "columns": ["그렇다", "그렇지 않다"],
        "required": REGIONS,
    },
}

#: Count-only table (복수응답): no base, no percentages.
COUNT_TABLE = {
    "표 3-2": {
        "question": "재해 당시 대피 방법에 대한 정보를 어떻게 들었습니까? (복수응답)",
        "columns": ["재난 문자", "TV·라디오", "마을 방송", "마을 주민",
                    "경찰·소방관 등 공무원", "기타", "듣지 못했다"],
        "required": REGIONS,
    }
}

#: What this repository CLAIMS each figure is. The script fails if the PDF
#: disagrees. These are the assertion, not the source.
PINS = {
    ("표 1-1", "전체"): (296, [(3, 1.0), (51, 17.2), (189, 63.9), (53, 17.9)]),
    ("표 1-5", "전체"): (300, [(63, 21.0), (141, 47.0), (50, 16.7), (26, 8.7), (20, 6.7)]),
    ("표 1-5", "영덕"): (100, [(36, 36.0), (39, 39.0), (11, 11.0), (7, 7.0), (7, 7.0)]),
    ("표 1-6", "전체"): (299, [(269, 90.0), (30, 10.0)]),
    ("표 1-6", "영덕"): (99, [(97, 98.0), (2, 2.0)]),
    ("표 3-1", "전체"): (297, [(185, 62.3), (112, 37.7)]),
    ("표 3-1", "영덕"): (100, [(48, 48.0), (52, 52.0)]),
    ("표 3-3", "전체"): (291, [(246, 84.5), (9, 3.1), (8, 2.7), (7, 2.4), (21, 7.2)]),
    ("표 3-3", "영덕"): (97, [(78, 80.4), (1, 1.0), (8, 8.2), (3, 3.1), (7, 7.2)]),
    ("표 3-4", "전체"): (278, [(167, 60.1), (46, 16.5), (42, 15.1), (11, 4.0), (12, 4.3)]),
    ("표 3-5", "전체"): (299, [(260, 87.0), (39, 13.0)]),
}

COUNT_PINS = {("표 3-2", "전체"): [112, 21, 144, 93, 27, 5, 36]}

#: A figure the report itself CITES from elsewhere rather than measures.
#: Kept separate so it can never be read as a survey finding.
SECONDARY = {
    "yeongdeok_casualties_total": 66,
    "yeongdeok_deaths": 10,
    "yeongdeok_deaths_mean_age": 84,
    "yeongdeok_deaths_max_age": 101,
    "cited_from": "영덕군 홈페이지, 「영덕 초대형산불 피해 및 대처사항」 2025-04-29 (보고서 p.9 각주 2)",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_pages(pdf: Path) -> list[str]:
    try:
        import pypdf
    except ImportError:  # pragma: no cover - depends on the optional extra
        sys.exit('pypdf is required to re-extract; pip install -e ".[evidence]"')
    reader = pypdf.PdfReader(str(pdf))
    return [(page.extract_text() or "") for page in reader.pages]


def _page_mapped(pages: list[str]) -> tuple[str, list[int]]:
    """All pages with EVERY space removed, plus a char -> page-number map.

    The report's tables are laid out so that ``extract_text`` returns each cell
    on its own line with stray spaces inside numbers and Korean words; removing
    whitespace entirely is what makes one regex match a table cell.
    """
    big, pmap = [], []
    for number, text in enumerate(pages, start=1):
        squeezed = re.sub(r"\s+", "", text)
        big.append(squeezed)
        pmap.extend([number] * len(squeezed))
    return "".join(big), pmap


def _definition_offset(big: str, table_id: str) -> int | None:
    """Offset of the table DEFINITION, not a prose cross-reference to it.

    The body text says "(표 1-5)" many pages before the table itself, so the
    first match is nearly always the wrong one. The definition is the marker
    followed closely by the report's own "(사례수)" column header.
    """
    marker = table_id.replace(" ", "") + "."
    for match in re.finditer(re.escape(marker), big):
        if "(사례수)" in big[match.end():match.end() + 300]:
            return match.start()
    return None


def parse_percent_table(big: str, pmap: list[int], table_id: str, ncols: int) -> dict:
    start = _definition_offset(big, table_id)
    if start is None:
        raise SystemExit(f"{table_id}: no table definition found in the PDF")
    segment = big[start:start + 1500]
    rows = {}
    for region in REGIONS:
        m = re.search(
            rf"{region}([\d,]+)\(100\.0%\)((?:[\d,]+\([\d.]+%\)){{{ncols}}})", segment
        )
        if not m:
            continue
        cells = [
            {"count": int(c.replace(",", "")), "percent": float(p)}
            for c, p in re.findall(r"([\d,]+)\(([\d.]+)%\)", m.group(2))
        ]
        rows[region] = {"base": int(m.group(1).replace(",", "")), "cells": cells}
    return {"page": pmap[start], "rows": rows}


def parse_count_table(pages: list[str], table_id: str, ncols: int) -> dict:
    """복수응답 tables carry no percentages, so the digits are only separated by
    spaces; squeezing whitespace here would fuse ``112 21 144`` into one number."""
    spaced = [re.sub(r"\s+", " ", t) for t in pages]
    marker = table_id + "."
    for number, text in enumerate(spaced, start=1):
        if marker not in text:
            continue
        blob = " ".join(spaced[number - 1:number + 1])
        segment = blob[blob.find(marker):][:900]
        rows = {}
        for region in REGIONS:
            m = re.search(rf"{region}\s+((?:\d+\s+){{{ncols - 1}}}\d+)", segment)
            if m:
                rows[region] = [int(x) for x in m.group(1).split()]
        if rows:
            return {"page": number, "rows": rows}
    raise SystemExit(f"{table_id}: no table found in the PDF")


def parse_secondary(pages: list[str]) -> dict:
    for number, text in enumerate(pages, start=1):
        flat = re.sub(r"\s+", " ", text)
        m = re.search(
            r"영덕군\s*인명\s*피해는\s*총\s*(\d+)\s*명.{0,40}?사망자\s*(\d+)\s*명의\s*"
            r"평균\s*연령이\s*(\d+)\s*세\s*,\s*최고령\s*(\d+)\s*세",
            flat,
        )
        if m:
            total, deaths, mean_age, max_age = (int(g) for g in m.groups())
            return {"page": number, "casualties_total": total, "deaths": deaths,
                    "deaths_mean_age": mean_age, "deaths_max_age": max_age}
    raise SystemExit("the 영덕 casualty sentence was not found in the PDF")


def check(tables: dict, counts: dict, secondary: dict) -> list[str]:
    """Every disagreement, collected — not the first one."""
    problems = []

    for table_id, spec in TABLES.items():
        rows = tables[table_id]["rows"]
        for region in spec["required"]:
            if region not in rows:
                problems.append(f"{table_id}/{region}: required row not parsed")
                continue
            row = rows[region]
            if len(row["cells"]) != len(spec["columns"]):
                problems.append(
                    f"{table_id}/{region}: {len(row['cells'])} cells, "
                    f"{len(spec['columns'])} columns"
                )
                continue
            # the table's own arithmetic: each count/base must equal its percent
            for name, cell in zip(spec["columns"], row["cells"]):
                got = 100.0 * cell["count"] / row["base"]
                if abs(got - cell["percent"]) > 0.1:
                    problems.append(
                        f"{table_id}/{region}/{name}: {cell['count']}/{row['base']} "
                        f"= {got:.2f}% but the report prints {cell['percent']}%"
                    )

    for (table_id, region), (base, cells) in PINS.items():
        row = tables[table_id]["rows"].get(region)
        if row is None:
            problems.append(f"PIN {table_id}/{region}: row missing")
            continue
        got = (row["base"], [(c["count"], c["percent"]) for c in row["cells"]])
        if got != (base, cells):
            problems.append(f"PIN {table_id}/{region}: PDF has {got}, repository claims {(base, cells)}")

    for (table_id, region), expected in COUNT_PINS.items():
        got = counts[table_id]["rows"].get(region)
        if got != expected:
            problems.append(f"PIN {table_id}/{region}: PDF has {got}, repository claims {expected}")

    for key in ("casualties_total", "deaths", "deaths_mean_age", "deaths_max_age"):
        expected = SECONDARY["yeongdeok_" + key]
        if secondary[key] != expected:
            problems.append(f"PIN secondary/{key}: PDF has {secondary[key]}, repository claims {expected}")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.pdf.exists():
        sys.exit(
            f"{args.pdf} is absent. It is a 3.4 MB third-party report under the "
            "git-ignored data/raw/, so a fresh clone does not have it; download it "
            f"from {SOURCE['url']} to re-extract. The committed JSON is what travels."
        )

    digest = sha256_of(args.pdf)
    if digest != SOURCE["sha256"]:
        sys.exit(
            f"sha256 mismatch: {args.pdf} digests to {digest}, not "
            f"{SOURCE['sha256']}. This is a different document; refusing to read it."
        )

    pages = read_pages(args.pdf)
    if len(pages) != SOURCE["pages"]:
        sys.exit(f"expected {SOURCE['pages']} pages, found {len(pages)}")

    big, pmap = _page_mapped(pages)
    tables = {
        tid: parse_percent_table(big, pmap, tid, len(spec["columns"]))
        for tid, spec in TABLES.items()
    }
    counts = {
        tid: parse_count_table(pages, tid, len(spec["columns"]))
        for tid, spec in COUNT_TABLE.items()
    }
    secondary = parse_secondary(pages)

    problems = check(tables, counts, secondary)
    if problems:
        print("REFUSING TO WRITE — the PDF and this repository disagree:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1

    out = {
        "_readme": (
            "Figures TRANSCRIBED by scripts/extract_survey_evidence.py from a "
            "third-party report, identified by the sha256 below. This project did "
            "NOT measure them and cannot reproduce them by re-running its pipeline, "
            "which is why they are absent from docs/NUMBERS.json. Read "
            "docs/evidence/greenpeace_2026_survey.md before quoting any of them."
        ),
        "built_by": "scripts/extract_survey_evidence.py",
        "built_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": SOURCE,
        "provenance": "third-party transcription; not derived by this project",
        "survey_design": {
            "n_respondents": 300,
            "regions": {"안동": 100, "영덕": 100, "의성": 100},
            "answering_bases_range": [291, 300],
            "note": (
                "Every table carries its own 사례수 base; they differ per question "
                "(291-300) because non-response differs per question. Percentages "
                "are always over that table's base, never over 300."
            ),
        },
        "tables": {
            tid: {
                "question": TABLES[tid]["question"],
                "columns": TABLES[tid]["columns"],
                "page": tables[tid]["page"],
                "rows": tables[tid]["rows"],
            }
            for tid in TABLES
        },
        "count_tables": {
            tid: {
                "question": COUNT_TABLE[tid]["question"],
                "columns": COUNT_TABLE[tid]["columns"],
                "page": counts[tid]["page"],
                "rows": counts[tid]["rows"],
                "note": "복수응답: counts only, no base and no percentages.",
            }
            for tid in COUNT_TABLE
        },
        "secondary_citation": {
            "_warning": (
                "NOT a survey finding. The report cites these from 영덕군's own "
                "notice; the survey sampled survivors, so the dead are by "
                "construction absent from every table above."
            ),
            "cited_from": SECONDARY["cited_from"],
            **secondary,
        },
        "unparsed": {
            "표 3-4/의성": (
                "The report's layout splits this row across a page break (counts on "
                "p.24, percentages on p.25), so count and percent are no longer "
                "interleaved. Recorded as unparsed rather than guessed; it is not a "
                "figure this project quotes."
            )
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # --out may point outside the repository (a scratch path, which is how an
    # independent reviewer re-runs this and diffs the result); relative_to would
    # raise there and report failure for a run that wrote the file correctly.
    try:
        shown = args.out.relative_to(REPO)
    except ValueError:
        shown = args.out
    print(f"wrote {shown}")
    print(f"  source sha256 {digest}")
    print(f"  {len(TABLES)} answer tables, {len(COUNT_TABLE)} count table, all pins agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
