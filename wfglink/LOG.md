# wfglink log

Append-only. Times are Asia/Shanghai (UTC+08:00). Each entry: goal, exact commands, parameters, results (numbers carry a NUMBERS.json key), decisions, next step. Failures are logged too.

## 2026-10-14T23:40+08:00 Planning and approval

- Goal: produce and get approval for the wfglink plan, then start section 15 (first actions).
- Commands:
  - `git rev-parse --show-toplevel` returned `/home/user/wildfireguardian`; branch `claude/practical-rubin-5vu12u`; README read.
  - Read-only research workflows (repo conventions, route logger search across all refs, science, computer vision, macOS platform), a licensed clip search with license verification, and a three-lens adversarial plan review. No files were written during planning.
- Parameters: none (planning only).
- Results:
  - Route logger: not present in any git ref; the repo only describes an ESP32 plus Quectel L76K GNSS device with planned CSV and GPX exports. Its schema is on the user's Mac.
  - Repo has no video or OpenCV code; wfglink copies only conventions.
  - Clip shortlist with verified licenses (PLAN.md section 13). No openly licensed Korean ember video was found.
  - No measured results yet, so no NUMBERS.json entries.
- Decisions (user, verbatim in docs/PROMPT.md): one week of continuous work; iPad Air and iPhone 13; push to the session branch with one draft PR; clips C1 to C13 approved, C10 tracking-only, C14 conditional, C15 pending KFS permission; dashcam file-mode check added; daily demo tags from M2; check A Thursday, check B Saturday; booth screen 2 m rule; any motorized platform for the LED test; black cloth hood.
- Decisions (mine, from the review): held-out mismatch suite supplies headline numbers; LED clips never used for tuning; ground homography never applied to airborne embers; approximate running median for live mode; booth clips with corner ArUco markers, Gray-coded frame index and held frames.
- Next step: scaffold (records, check scripts), Python 3.12 venv with pinned requirements, Qt offscreen and Pretendard smoke test, first commit and draft PR, then M0 Mac check A tooling.

## 2026-10-14T23:48+08:00 Scaffold and environment (M0 start)

- Goal: section 15 first actions: folder, records, guard scripts, pinned environment, smoke tests.
- Commands:
  - `python3.12 -m venv wfglink/.venv`, then `wfglink/.venv/bin/python -m pip install -r wfglink/requirements.txt` and `pip install -e wfglink --no-deps`.
  - First Qt import failed with `ImportError: libEGL.so.1`; fixed in the container (not the repo) with `apt-get install libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libglib2.0-0`.
  - Pretendard 1.3.9 taken from the npm tarball (SHA-256 in data/SOURCES.md); four weights vendored in assets/fonts with the OFL license.
  - `python -m wfglink doctor`, `python -m pytest -q`, `python3 scripts/check_staged.py`, `python3 scripts/check_docs.py`.
- Parameters: pins in requirements.txt (numpy 2.5.4, scipy 1.18.1, opencv-contrib-python-headless 4.14.0.94, PySide6 6.12.0, av 19.0.1, pyarrow 26.0.0, pandas 3.0.6, PyYAML 6.0.3, matplotlib 3.11.2, pytest 9.1.1, pyobjc-framework-AVFoundation 12.2.2 on macOS only). Full container environment in constraints-linux-x86_64.txt.
- Results:
  - doctor reports ok: Qt offscreen platform works, Pretendard resolves as the UI font, OpenCV ArUco is present, PyAV decodes H.264, HEVC, AV1 (libdav1d) and VP9 and encodes libx264.
  - The smoke tests pass, and check_docs flagged every planted error in a scratch copy (em dash, wrong tagged value, untagged result, dirty entry).
- Decisions: check_docs treats README "Current status" and LOG "Results" bullets as result sections; numbers there need a NUMBERS.json tag. A run is dirty only if wfglink src, configs, scripts, pyproject or requirements have uncommitted changes, so writing results does not dirty its own run.
- Next step: commit and push, open the draft PR, then build Mac check A tooling.
