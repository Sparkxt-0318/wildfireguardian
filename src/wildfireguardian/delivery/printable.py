"""A4 dispatch sheet for the 이장 — HTML, then PDF.

Round-3 PHASE 3. The most important of the three channels.

WHY PAPER
---------
The 2025 Yeongnam survey (n=300) put the emergency SMS reception rate in
Yeongdeok at 48 %. A sheet in a 이장's hand does not depend on a phone being
charged, carried, in coverage, or legible to someone who cannot read a small
screen without glasses.

DESIGN CONSTRAINTS
------------------
* **One A4 page per village.** A second page gets separated from the first.
* **14 pt minimum body text**, larger for the numbers that matter.
* **Legible photocopied in black and white.** No colour is load-bearing: every
  status is carried by a word and a border weight as well as a shade, because
  village printers are monochrome and the sheet will be copied.
* Unreachable points are set apart, not merely tinted.
* Header carries generation time, commit and the "spatial cluster, not 행정리"
  statement. Footer carries two fixed cautions.

PDF conversion uses headless Chrome. If no engine is available the HTML is still
written and the caller is told; the HTML is the canonical artifact.
"""

from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

#: Candidate headless-Chrome binaries, in order.
_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
)

FOOTER_LINES = (
    "본 목록은 예측에 기반한 참고 자료이며 최종 판단은 현장에서 하십시오.",
    "본 목록은 600분 보행 예산 기준이며, 실제 경보 시간에서는 도달 불가 지점이 크게 늘어납니다.",
)

_CSS = """
@page { size: A4 portrait; margin: 11mm 10mm 10mm 10mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: "Apple SD Gothic Neo", "AppleGothic", "NanumGothic",
               "Malgun Gothic", sans-serif;
  font-size: 14pt; line-height: 1.28; color: #000; background: #fff;
}
.hdr { border-bottom: 3px solid #000; padding-bottom: 4px; margin-bottom: 7px; }
.hdr h1 { font-size: 25pt; margin: 0 0 2px 0; letter-spacing: -0.5px; }
.hdr .sub { font-size: 14pt; font-weight: bold; margin-bottom: 3px; }
.meta { font-size: 10.5pt; line-height: 1.35; }
.meta b { font-weight: bold; }
.warnbox {
  border: 2px solid #000; padding: 4px 7px; margin: 6px 0;
  font-size: 12pt; font-weight: bold;
}
h2 { font-size: 16pt; margin: 9px 0 4px 0; padding-bottom: 2px;
     border-bottom: 2px solid #000; }
table { width: 100%; border-collapse: collapse; font-size: 14pt; }
th, td { border: 1px solid #000; padding: 3px 5px; text-align: left;
         vertical-align: top; }
th { background: #ddd; font-weight: bold; font-size: 12.5pt; }
td.num { text-align: right; font-variant-numeric: tabular-nums;
         white-space: nowrap; }
td.big { font-size: 16pt; font-weight: bold; }
tr.unreach td { border-top: 3px solid #000; border-bottom: 3px solid #000;
                background: #eee; }
.tag { display: inline-block; border: 2px solid #000; padding: 0 4px;
       font-size: 11.5pt; font-weight: bold; }
.blank { color: #000; font-weight: bold; }
.ftr { margin-top: 9px; padding-top: 5px; border-top: 3px solid #000;
       font-size: 12pt; font-weight: bold; line-height: 1.35; }
.ftr div { margin-bottom: 2px; }
.sig { margin-top: 6px; font-size: 12pt; }
.sig span { display: inline-block; border-bottom: 1px solid #000;
            min-width: 95px; margin-right: 14px; }
"""


def _fmt_remaining(v) -> tuple[str, str]:
    """Return (display, urgency word) for a closing-window value in minutes."""
    if v is None or v != v:                       # None or NaN
        return "확인 불가", ""
    if v <= 0:
        return "이미 경과", "즉시"
    return f"{int(round(v))}분", ("긴급" if v < 30 else "")


def render_html(village, *, generated_at: str, git_commit: str,
                config_hash: str, source_file: str, n_total_dispatch: int,
                n_total_unreachable: int, extra_label: str | None = None) -> str:
    """Render one village's A4 sheet as self-contained HTML.

    ``extra_label`` renders as a second bordered banner directly under the
    "not 행정리" one. It exists so a sheet built from the 2026-07-24 re-run can
    say on its face that its figures differ from the ones the submission cites.
    """
    dispatch = [p for p in village.points if not p.get("unreachable")]
    unreach = [p for p in village.points if p.get("unreachable")]
    dispatch.sort(key=lambda p: (p.get("closing_window_min") is None,
                                 p.get("closing_window_min", 1e9)))

    e = html.escape
    rows = []
    for i, p in enumerate(dispatch, start=1):
        disp, urg = _fmt_remaining(p.get("closing_window_min"))
        route = p.get("route_note") or "진입 경로 확인 필요"
        rows.append(
            f"<tr><td class='num'>{i}</td>"
            f"<td>{e(p.get('label', '-'))}</td>"
            f"<td class='num big'>{e(disp)}"
            + (f" <span class='tag'>{e(urg)}</span>" if urg else "")
            + f"</td><td>{e(route)}</td>"
            f"<td class='blank'>□</td></tr>")
    if not rows:
        rows.append("<tr><td colspan='5'>이 마을에는 구조 요청 지점이 "
                    "없습니다.</td></tr>")

    urows = []
    for i, p in enumerate(unreach, start=1):
        reason = p.get("reason_ko") or "차량 진입로가 화재로 차단됨"
        urows.append(
            f"<tr class='unreach'><td class='num'>{i}</td>"
            f"<td>{e(p.get('label', '-'))}</td>"
            f"<td>{e(reason)}</td>"
            f"<td class='blank'>□</td></tr>")

    unreach_block = ""
    if urows:
        unreach_block = (
            "<h2>■ 차량 도달 불가 지점 — 별도 조치 필요</h2>"
            "<table><thead><tr><th style='width:7%'>번호</th>"
            "<th style='width:33%'>위치</th><th>사유</th>"
            "<th style='width:9%'>확인</th></tr></thead>"
            f"<tbody>{''.join(urows)}</tbody></table>")

    footer = "".join(f"<div>{e(line)}</div>" for line in FOOTER_LINES)
    extra_block = (f'<div class="warnbox">※ {e(extra_label)}</div>'
                   if extra_label else "")

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>{e(village.name)} 출동 목록</title><style>{_CSS}</style></head>
<body>
<div class="hdr">
  <h1>{e(village.name)} 출동 목록</h1>
  <div class="sub">구조 요청 {len(dispatch)}곳 · 도달 불가 {len(unreach)}곳</div>
  <div class="meta">
    생성 {e(generated_at)} · 커밋 <b>{e(git_commit[:12])}</b> ·
    설정 <b>{e(config_hash[:12])}</b><br>
    산출물 {e(source_file)} · 전체 출동 {n_total_dispatch}곳 중
    본 목록 {len(dispatch)}곳, 전체 도달 불가 {n_total_unreachable}곳 중
    본 목록 {len(unreach)}곳
  </div>
</div>

<div class="warnbox">
  ※ 이 「마을」은 행정리가 아니라 좌표 기반 공간 군집입니다.
  실제 행정리 경계와 다를 수 있습니다.
</div>
{extra_block}

<h2>■ 구조 필요 지점 — 남은 시간 순</h2>
<table><thead><tr>
  <th style="width:7%">번호</th><th style="width:30%">위치</th>
  <th style="width:17%">남은 시간</th><th>진입 가능 경로</th>
  <th style="width:9%">확인</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>

{unreach_block}

<div class="ftr">{footer}</div>
<div class="sig">확인자 <span>&nbsp;</span> 시각 <span>&nbsp;</span>
  연락처 <span>&nbsp;</span></div>
</body></html>"""


def find_chrome() -> str | None:
    for c in _CHROME_CANDIDATES:
        if Path(c).exists():
            return c
        w = shutil.which(c)
        if w:
            return w
    return None


def html_to_pdf(html_path: Path, pdf_path: Path, *, timeout_s: float = 45.0) -> dict:
    """Convert with headless Chrome. Never raises; reports what happened.

    Chrome writes the PDF and then, on this platform, does not always exit —
    ``subprocess.run`` would block until its timeout even though the output has
    been complete for seconds. So the process is launched detached and the
    OUTPUT FILE is polled: once it exists and its size has stopped changing,
    the conversion is done and Chrome is terminated. Waiting on the artifact
    rather than on the process turns a 45-second hang into ~2 seconds and makes
    a non-exiting Chrome a non-issue rather than a failure.
    """
    chrome = find_chrome()
    if chrome is None:
        return {"ok": False, "engine": None,
                "reason": "no headless Chrome/Chromium found; HTML written only"}
    pdf_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
               "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", "--disable-sync",
               "--disable-background-networking", "--virtual-time-budget=4000",
               f"--user-data-dir={tmp}", "--no-pdf-header-footer",
               f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE)
        deadline = time.monotonic() + timeout_s
        last_size, stable = -1, 0
        try:
            while time.monotonic() < deadline:
                if pdf_path.exists():
                    size = pdf_path.stat().st_size
                    if size > 0 and size == last_size:
                        stable += 1
                        if stable >= 3:          # ~0.45 s unchanged => complete
                            break
                    else:
                        stable = 0
                    last_size = size
                elif proc.poll() is not None:
                    break                        # exited without producing a PDF
                time.sleep(0.15)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        err = b""
        try:
            err = proc.stderr.read() or b"" if proc.stderr else b""
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "engine": chrome,
                "reason": (err.decode(errors="replace")[-300:] or "no PDF produced")}
    return {"ok": True, "engine": chrome, "bytes": pdf_path.stat().st_size,
            "n_pages": pdf_page_count(pdf_path)}


def pdf_page_count(pdf_path: Path) -> int | None:
    """Page count without a PDF library: count /Type /Page objects."""
    try:
        raw = pdf_path.read_bytes()
    except OSError:
        return None
    import re
    n = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    if n:
        return n
    m = re.findall(rb"/Count\s+(\d+)", raw)
    return int(m[0]) if m else None


__all__ = ["FOOTER_LINES", "find_chrome", "html_to_pdf", "pdf_page_count",
           "render_html"]
