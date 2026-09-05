# R6 — Automation tooling survey for the WildfireGuardian agent loop

Date: 2026-09-03. Scope: what to bolt onto (a) Claude Code cloud routines, (b) GitHub Actions on `Sparkxt-0318/wildfireguardian`, (c) the vendored paperthin skills. Ratings are for THIS project (finals 2026-10-18, then ISEF selection, then an IEEE paper), not in general. Nothing under the repo was modified.

## 0. Facts that constrain every recommendation

Verified locally (read-only) unless marked otherwise.

| Fact | Consequence |
|---|---|
| **There is no `.github/` directory at all.** Zero CI. `make verify` (12 gates, NUMBERS.json 254/254) and 1,116-test pytest run only on the student's laptop or inside an agent sandbox. | A routine that opens a PR today gets no red/green signal. CI is the first thing to add; everything else hangs off it. |
| Reference env is conda-forge `wfg311` (Python 3.11.15, `docs/ENVIRONMENT.md`), but Session 18 verified the same pins install from PyPI wheels on Linux aarch64 (`requirements.txt` header). Cloud VM is Ubuntu 24.04 x86_64, 4 vCPU / 16 GB / 30 GB, Python + `uv` + `pytest` + `ruff` pre-installed ([cloud-environments](https://code.claude.com/docs/en/cloud-environments)). | `uv pip install -r requirements.txt` is viable in both the routine setup script and GitHub Actions. No conda needed in CI. |
| Suite: 1,116 passed / 3 skipped / 1 xfailed (`docs/SESSION22_REPORT.md`), 63 test files, 893 `def test_`, 1,293 cached node ids. Wall time is **UNVERIFIED** (no `--durations` record anywhere in docs). ~20 tests skip when artifacts/optional deps are absent (`tests/test_operator_screen.py`, `test_delivery.py`, `test_service_layer.py`). | CI must count skips and fail above the 3-skip baseline. `ENVIRONMENT.md`: "A skip is not a pass." pytest-xdist `-n 4` matches the 4-vCPU runner. |
| Tracked repo is 97 MB / 3,523 files; largest tracked blobs are DEM `.tif` (7.5 MB) and OSM `.graphml.gz`; `data/raw` (1.3 GB) is git-ignored and regenerable; `data/snapshots/MANIFEST.json` already sha256-pins external inputs (`make snapshot-verify`). | Data versioning is already solved for what matters. DVC/lakeFS would duplicate `snapshot_external.py`. |
| `docs/HANDOFF_ROUND3.md` §5: "Never push to `Main`. All work stays on `round3-dev`." Routines clone the **default branch** (`origin/HEAD -> Main`) unless the prompt says otherwise, and can only push to `claude/`-prefixed branches ([routines](https://code.claude.com/docs/en/routines)). | Every routine prompt must start with `git checkout round3-dev` (or the user flips the default branch). PRs from routines target `round3-dev`. CI triggers must include `claude/**` and `round3-dev`. |
| Cloud sessions sit behind an **HTTP/HTTPS-only security proxy**; "All outbound internet traffic ... passes through this proxy." Trusted allowlist covers PyPI, conda, GitHub, Docker, `*.googleapis.com` but **not** NASA FIRMS, Overpass, OpenTopography, `api.semanticscholar.org`, `export.arxiv.org`. GitHub GraphQL is pinned to PR operations; **Projects v2 is unreachable** from a routine. Setup script must finish in ~5 min; cache expires ~7 days ([cloud-environments](https://code.claude.com/docs/en/cloud-environments)). | Raw SMTP (`smtp.gmail.com:465`, which `delivery/email.py` uses) cannot work from a routine. Literature/FIRMS routines need a **Custom** network allowlist. GitHub Projects is out; Issues (REST via `gh`) is in. |
| Routines: Pro/Max/Team/Enterprise; min interval 1 h; "draw down subscription usage the same way interactive sessions do" plus a daily run cap; connectors (claude.ai MCP) included by default and "Claude can use every tool from an included connector, including writes, without asking" ([routines](https://code.claude.com/docs/en/routines)). | A Gmail connector inside a routine is the cheapest email path. Prune connectors per routine. |
| claude-code-action accepts `claude_code_oauth_token` from `claude setup-token` on Pro/Max; "If you authenticate with an OAuth token, runs use your Claude subscription instead of API billing" ([github-actions](https://code.claude.com/docs/en/github-actions)). Actions minutes are "free and unlimited on public repositories" ([GitHub docs](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)). | @claude on issues/PRs and a PR-review workflow cost nothing beyond subscription usage. |
| Anthropic's managed **Code Review** product is Team/Enterprise only, $15–25 per review ([code-review](https://code.claude.com/docs/en/code-review)). | Not for this account. Use the action's review workflow instead. |
| Already installed: paperthin (re0-loop/plan/memo/work, nba, catchup, hate, prism, factchk, mandela, sip, shower, ssotize, autobahn, ...), plus `.claude/skills/` ponytail (YAGNI enforcer), systematic-debugging, verification-before-completion, ui-ux-pro-max, design-system, slides; PreToolUse hook `rtk-rewrite.sh`. | The methodology layer is saturated. obra/superpowers overlaps ~80% (TDD, brainstorm, review loops) with paperthin + ponytail; adding it would create exactly the near-duplicate-skill slop paperthin's README warns about. |
| `notebooks/03_yeongdeok_real_validation.ipynb` has 10 output cells committed; `05_...` has 4. No `CITATION.cff`, no DOI. | nbstripout and CITATION.cff are trivially cheap wins. |

## 1. Rating table

Value = usefulness for THIS project 1–5. Cost = integration effort/risk 1 (trivial) – 5 (weeks or fragile). Rec = **yes** (adopt now) / **later** / **no**.

| # | Tool | Value | Cost | Rec | One-line reason |
|---|---|---|---|---|---|
| 1 | GitHub Actions CI (`pytest -n 4` + `make verify`), via `uv` | 5 | 2 | **yes** | Nothing else has a signal without it. Free on public repo. |
| 2 | uv (`astral-sh/setup-uv`) for env bootstrap | 4 | 1 | **yes** | Seconds instead of minutes; pre-installed in the cloud VM. |
| 3 | pytest-xdist | 3 | 1 | **yes** | 4-vCPU runners; ship as part of #1. Watch for tests that share `data/cache` paths (`test_osm_cache_isolation.py` exists, so isolation is already a concern the suite tests). |
| 4 | pre-commit + ruff (check+format) + nbstripout + hygiene hooks | 4 | 2 | **yes** | `[tool.ruff]` already in pyproject; ruff is ponytail-compatible. Start non-blocking on the legacy code. |
| 5 | anthropics/claude-code-action: `@claude` + PR review on `pull_request` | 4 | 2 | **yes** | Second reviewer on every routine PR, subscription-billed, zero API key. |
| 6 | GitHub Issues as the backlog (labels + templates; `gh` from routines) | 4 | 1 | **yes** | Routines can read/write Issues over REST; `nba`/`catchup` skills get a durable state source instead of `HANDOFF_ROUND3.md` §4 sprawl. |
| 7 | GitHub Projects (v2) | 2 | 3 | **no** | GraphQL-only; the cloud proxy blocks it. Issues + labels cover it. |
| 8 | CITATION.cff + Zenodo DOI on a tagged release | 4 | 1 | **yes** | Rubric "제출 자료: 출처 명시"; IEEE paper needs a citable software artifact; ISEF judges check reproducibility. |
| 9 | Playwright smoke + screenshot of `web/finals.html` in CI | 4 | 2 | **yes** | The offline single file *is* the finals deliverable. Smoke (no console errors, panels present, Korean fonts loaded) now; pixel-diff later. |
| 10 | Hypothesis property tests | 3 | 2 | **yes** | Routing invariants (path cost ≥ 0, monotone in hazard, `DiGraph` asymmetry that Session 22 found by hand) and Rothermel monotonicity are exactly property-shaped. Pure code, no infra. |
| 11 | Weekly literature routine (Semantic Scholar recommendations + arXiv API) | 3 | 2 | **yes** | Feeds "difference from prior research" (20 pts) and the IEEE related-work section; needs a Custom allowlist. |
| 12 | Claude Code routine vs GitHub Actions cron | — | — | see §3 | Use both, for different jobs. |
| 13 | Dependabot (github-actions ecosystem only) | 2 | 1 | later (fold into #1) | Python pins are scientific constraints (`osmnx==2.0.7` matches snapshot `created_with`); never let a bot float them. |
| 14 | Renovate | 1 | 3 | **no** | Overkill for one repo with frozen pins. |
| 15 | pyright / basedpyright | 2 | 4 | later | Untyped scientific codebase: thousands of findings on day one = noise the loop will "fix" instead of doing science. |
| 16 | pandera | 3 | 2 | later | Schema for the OOF parquet/csv.gz and `NUMBERS.json` inputs would strengthen `verify_numbers.py`; do it when a schema bug actually bites. |
| 17 | Great Expectations | 1 | 4 | **no** | 100+ deps, platform-shaped. pandera is the right size. |
| 18 | DVC | 2 | 3 | later | Only if `data/raw` (1.3 GB) must be shared with a judge/collaborator; Google Drive remote is free. Snapshot store + MANIFEST already gives provenance. |
| 19 | lakeFS | 0 | 5 | **no** | Server + metadata DB for one student repo. |
| 20 | MLflow / W&B | 1 | 3 | **no** | 6 fires, LOGO-CV, ~260 registry-gated numbers re-derived from committed JSON by `make verify`. That *is* the experiment tracker, and it works offline at the booth. W&B adds a cloud the judges can't see. |
| 21 | codecov | 2 | 2 | later | Needs a token from the user; coverage % is not a rubric item. `pytest --cov` in CI artifacts is enough. |
| 22 | SonarCloud | 1 | 2 | **no** | Free for OSS, but generic Python smells on a project with 12 bespoke gates; more bot noise on PRs. |
| 23 | GitHub Copilot code review | 3 | 1 | later | Free for verified students (Copilot Student: 200 AI credits/mo, code review included, since 2026-03-12). Requires GitHub Education verification (days). Zero-cost third opinion once verified. |
| 24 | Codex cloud (auto PR review) | 3 | 2 | later | Real second opinion from a different model family, but needs ChatGPT Plus ($20/mo). Only if already subscribed. |
| 25 | Cursor Bugbot | 2 | 3 | **no** | $1–1.50 per PR on top of Pro; duplicative. |
| 26 | Devin | 1 | 4 | **no** | Opaque quotas; an autonomous *editor*, not a reviewer; would collide with the Claude routine on branches. |
| 27 | Jules | 2 | 2 | **no** (for now) | Free 15 tasks/day, but it opens PRs, it doesn't review; two autonomous editors on one repo = merge churn. |
| 28 | OpenHands PR Review Action | 2 | 3 | **no** | Needs an LLM API key (pay-per-review), Docker runtime on the runner; the Claude action already reviews. |
| 29 | SWE-agent / mini-SWE-agent | 1 | 3 | **no** | Research benchmark tool; no reviewer mode; SWE-agent itself is in maintenance ("superseded by mini-swe-agent"). |
| 30 | Aider in CI | 1 | 3 | **no** | Another editor in the loop; nothing it does that the routine cannot. |
| 31 | obra/superpowers and other skill libraries | 2 | 2 | **no** | Overlaps paperthin + ponytail + systematic-debugging + verification-before-completion. Adding it is the anti-pattern paperthin exists to prevent. Cherry-pick one skill file only if a gap is found. |
| 32 | anthropics/skills (official) | 2 | 1 | later | `pdf`/`docx`/`pptx` skills already present in this environment; vendor `docx` only when the IEEE/KCF documents are generated in-loop. |
| 33 | Papers with Code | 0 | — | **no** | Dead: sunset 2025-07-24, redirects to HF Trending Papers. |
| 34 | Semantic Scholar API | 4 | 1 | **yes** (#11) | Recommendations endpoint takes positive/negative paper IDs; 1 rps with a free key. |
| 35 | arXiv API/RSS listing | 3 | 1 | **yes** (#11) | `export.arxiv.org/api/query` for `cs.LG`/`physics.ao-ph` keyword queries. |
| 36 | Elicit / Consensus / NotebookLM | 2 | 1 | **no** (as automation) | Interactive products, no loop-usable API on free tiers. Consensus MCP is already attached in this environment for ad-hoc use; NotebookLM is fine for the student's own reading. |
| 37 | LaTeX CI (`xu-cheng/latex-action@v4`) | 3 | 1 | later | The moment `paper/main.tex` exists. Snippet in §5. |
| 38 | Overleaf git sync | 1 | 2 | **no** | Premium-only feature; the repo is the source of truth, Overleaf is optional. |
| 39 | marp / reveal.js slide CI | 1 | 2 | **no** | Finals are a booth demo on `finals.html`, not a deck; `slides` skill already exists for the ISEF stage. |
| 40 | Lighthouse | 1 | 2 | **no** | Performance scores for an offline `file://` page are meaningless. |
| 41 | axe-core (via Playwright) | 3 | 1 | later | One `@axe-core/playwright` call once #9 exists; the CLAUDE.md already demands WCAG AA for the operator console. |
| 42 | git-cliff | 2 | 1 | later | Generate `CHANGELOG.md` at the finals freeze tag; requires the loop to write conventional commits (paperthin `re0-git` helps). |
| 43 | semantic-release | 0 | 3 | **no** | Auto version bumps + pushes to the default branch = violates "never push Main"; nothing is published to a package index. |
| 44 | Email: GitHub built-in notifications | 4 | 0 | **yes** | Free: PR opened, review posted, workflow failed — already emails the repo owner. |
| 45 | Email: Gmail connector inside a routine | 4 | 1 | **yes** | Routine prompt ends with "send a 10-line digest via the Gmail connector". No allowlist change, no secret. |
| 46 | Email: `dawidd6/action-send-mail` + Gmail app password | 2 | 2 | later | Works (smtp.gmail.com:465), but it's one more long-lived credential in the repo for what GitHub notifications already do. |
| 47 | Email: SendGrid | 0 | — | **no** | Free tier ended 2025-05-27; $19.95/mo entry. |
| 48 | Email: Resend/Brevo HTTP API from a routine | 2 | 2 | later | Only if the Gmail connector is unavailable: needs Custom allowlist + API credential. |
| 49 | nbstripout | 3 | 1 | **yes** (#4) | 14 output cells committed today; diffs on `.ipynb` are unreadable for reviewers. |

## 2. Adopt now — the shortlist (8 items) with exact config

Order matters: 1 → 2 → 3 gives the loop a signal; 4–8 can land in any order. All files go on `round3-dev` (or a `claude/` branch → PR to `round3-dev`), never `Main`, per `HANDOFF_ROUND3.md` §5.

### 2.1 CI: `.github/workflows/ci.yml` (uv + pytest-xdist + make verify)

```yaml
name: ci
on:
  push:
    branches: [round3-dev, "claude/**"]
  pull_request:
    branches: [round3-dev, Main]
  workflow_dispatch:
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-latest      # 4 vCPU / 16 GB, free & unlimited on public repos
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
          cache-dependency-glob: "requirements.txt"
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install (exact pins, PyPI wheels; Session 18 verified this path on Linux)
        run: |
          uv pip install --system -r requirements.txt
          uv pip install --system -e . --no-deps
          uv pip install --system pytest-xdist "xgboost>=2.0"   # legacy test imports xgboost unguarded
      - name: Declared-deps + env gates
        run: |
          make env-check
          make verify
      - name: Tests (parallel, machine-readable)
        run: |
          python -m pytest -q -n 4 -ra --durations=25 \
            --junitxml=reports/junit.xml
      - name: Fail if skips exceed the 3-skip baseline ("a skip is not a pass")
        if: always()
        run: |
          python - <<'EOF'
          import xml.etree.ElementTree as ET, sys
          r = ET.parse("reports/junit.xml").getroot()
          s = int(r.get("skipped") or sum(int(t.get("skipped",0)) for t in r))
          print("skipped =", s); sys.exit(1 if s > 3 else 0)
          EOF
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: junit, path: reports/ }
```

Notes:
- Do **not** run `make snapshot-verify` or `baseline-verify` until the first run shows whether every artifact they hash is tracked (they may reference git-ignored files; `docs/artifact_manifest.json` says which). Add them as a second job after that.
- The first run's `--durations=25` tells you the real wall time (UNVERIFIED today). If > 15 min, split with `pytest-split` or mark the OSM/real-graph tests `@pytest.mark.slow` and run them nightly.
- `make finals` needs `networkx, numpy, pyproj, rasterio, PIL` — all in `requirements.txt`, so add `make finals` as a third job once #2.6 exists.
- Optional add-on, `.github/dependabot.yml` limited to Actions (never Python pins):
  ```yaml
  version: 2
  updates:
    - package-ecosystem: github-actions
      directory: /
      schedule: { interval: monthly }
  ```

### 2.2 pre-commit: ruff + nbstripout + hygiene

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ["--maxkb=8000"]     # the 7.5 MB DEM tif is the largest tracked file today
      - id: no-commit-to-branch
        args: ["--branch", "Main"]  # enforces HANDOFF §5.1 mechanically
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.5                    # latest tag as of 2026-09-03
    hooks:
      - id: ruff-check
        args: ["--fix", "--exit-non-zero-on-fix"]
      - id: ruff-format
  - repo: https://github.com/kynan/nbstripout
    rev: 0.9.1
    hooks:
      - id: nbstripout
```

Add to `pyproject.toml` (extending the existing `[tool.ruff]`):
```toml
[tool.ruff.lint]
# Start narrow so the legacy tree is green on day one; widen deliberately.
select = ["E9", "F63", "F7", "F82", "F401", "F841", "I"]
exclude = ["notebooks", "external", "cache", "outputs"]
```
CI job (append to `ci.yml`):
```yaml
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - uses: pre-commit/action@v3.0.1
```
Why narrow: `ruff --select ALL` on 115 scripts + `src/` will produce hundreds of findings and the routine will spend runs "fixing" style instead of science. `verification-before-completion` + `sip` already require running the repo's own checks; pre-commit just makes those checks the same on every machine. nbstripout: strips the 14 committed output cells on the next touch; if the outputs are load-bearing evidence, export them to `docs/figures/` first (never regenerate existing figures, §5.3).

### 2.3 `@claude` + PR review via `anthropics/claude-code-action@v1` (subscription token)

One-time, by the student: `claude setup-token` → repo secret `CLAUDE_CODE_OAUTH_TOKEN`; install the Claude GitHub App on the repo (`/install-github-app` does both). Routine PRs are authored by the student's GitHub identity, so the action's "human actor" check passes.

`.github/workflows/claude.yml`:
```yaml
name: claude
on:
  issue_comment: { types: [created] }
  pull_request_review_comment: { types: [created] }
  issues: { types: [opened, assigned] }
jobs:
  claude:
    if: contains(github.event.comment.body || github.event.issue.body, '@claude')
    runs-on: ubuntu-latest
    permissions: { contents: write, pull-requests: write, issues: write, id-token: write, actions: read }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 1 }
      - uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          claude_args: "--max-turns 30"
```

`.github/workflows/claude-review.yml` (independent second reviewer for every routine PR):
```yaml
name: claude-review
on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]
    branches: [round3-dev, Main]
jobs:
  review:
    if: github.event.pull_request.draft == false
    runs-on: ubuntu-latest
    permissions: { contents: read, pull-requests: read, issues: read, id-token: write }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 1 }
      - uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          plugin_marketplaces: "https://github.com/anthropics/claude-code.git"
          plugins: "code-review@claude-code-plugins"
          prompt: "/code-review:code-review --comment ${{ github.repository }}/pull/${{ github.event.pull_request.number }}"
          claude_args: '--allowedTools "mcp__github_inline_comment__create_inline_comment"'
```
Add a root `REVIEW.md` is *not* read by this path (only by the Team/Enterprise product); put review rules in `CLAUDE.md` instead, e.g. "Flag any PR that touches a file listed in `docs/HANDOFF_ROUND3.md` §5 or changes a committed artifact under `data/processed/`." Runs use subscription usage, so cap `--max-turns` and skip drafts.

### 2.4 GitHub Issues as the loop's backlog (not Projects)

- Labels: `phase/finals`, `phase/isef`, `phase/ieee`, `kind/science`, `kind/demo`, `kind/paper`, `risk/never-do` (anything touching §5), `needs-human` (the routine may not resolve alone).
- `.github/ISSUE_TEMPLATE/task.yml` with fields: goal, rubric line it serves (from 붙임1), acceptance command (`make verify`, a test name), never-do items touched.
- Routine prompt fragment: "Read open issues with `gh issue list --label phase/finals --json number,title,body`. Pick one by `nba`. Work on `round3-dev` in a `claude/` branch. Open a PR with `Closes #N`. Do not close issues labeled `needs-human`."
- Migrate `HANDOFF_ROUND3.md` §4 open items into issues once, by the user (they hold the context; the `ssotize` skill then points §4 at the issue list).
- `gh` inside the cloud VM authenticates through the GitHub proxy with no token; Projects v2 (GraphQL) returns 403 there, which is why Projects is on the do-not list.

### 2.5 `CITATION.cff` + Zenodo DOI

`CITATION.cff` at repo root (Zenodo reads it at release time):
```yaml
cff-version: 1.2.0
message: "If you use this software, please cite it as below."
title: "WildfireGuardian: wildfire spread forecasting coupled to household-level evacuation and rescue routing"
type: software
authors:
  - family-names: Park
    given-names: Siyeong
    affiliation: "Shanghai American School Puxi"
version: 0.1.0-alpha
date-released: 2026-10-01     # set at the finals freeze
repository-code: "https://github.com/Sparkxt-0318/wildfireguardian"
license: MIT
keywords: [wildfire, evacuation-routing, rothermel, korea, disaster-response]
```
Process (user-only, needs a browser login): zenodo.org → GitHub integration → toggle the repo → create a GitHub Release (e.g. `v0.1.0-finals`) from `Main` after the user merges `round3-dev`. Zenodo mints a versioned DOI + a concept DOI; paste the concept DOI badge into `README.md` and the `doi:` field of `CITATION.cff` on the next release. Note `docs/NUMBERS.json` gates prose: the DOI string is not a number, but run `make verify` after editing README anyway.

### 2.6 Playwright smoke test of `web/finals.html` (offline demo)

`tests/e2e/finals.spec.ts` (Node, kept out of the Python suite so `pytest` stays pure):
```ts
import { test, expect } from '@playwright/test';
import path from 'path';
const url = 'file://' + path.resolve('web/finals.html');
test('finals.html renders offline with no console errors and Korean glyphs', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.route('**/*', r => r.request().url().startsWith('file://') ? r.continue() : r.abort()); // enforce offline
  await page.goto(url);
  await expect(page.locator('body')).toContainText('산불');            // any Korean anchor string in the screen
  const fontsOk = await page.evaluate(async () => { await (document as any).fonts.ready; return (document as any).fonts.status === 'loaded'; });
  expect(fontsOk).toBeTruthy();
  expect(errors, errors.join('\n')).toEqual([]);
  await page.screenshot({ path: 'reports/finals.png', fullPage: true });
});
```
Workflow job:
```yaml
  finals-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get update && sudo apt-get install -y fonts-nanum fonts-noto-cjk   # no tofu boxes in screenshots
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: npm i -D @playwright/test && npx playwright install --with-deps chromium
      - run: npx playwright test tests/e2e --reporter=line
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: finals-screenshot, path: reports/finals.png }
```
The `route` abort is the important line: it proves the 2.0 MB single file has no hidden network dependency, which is exactly the no-wifi booth condition. Pixel regression (`toHaveScreenshot`) is deferred: Linux-vs-macOS rendering differs and the baseline would churn; a human looks at the artifact PNG.

### 2.7 Hypothesis property tests (no infra)

`pip`/`uv` add `hypothesis` to the `dev` extra. Three properties worth writing first, each targeting a bug class the project has already met:
```python
from hypothesis import given, settings, strategies as st
import numpy as np

# 1. Rothermel-style spread rate is monotone non-decreasing in wind speed and non-increasing in fuel moisture
@given(wind=st.floats(0, 30), moisture=st.floats(0.02, 0.35))
def test_ros_monotone(wind, moisture):
    from wildfireguardian.spread import ros      # adapt to the real symbol
    assert ros(wind + 1.0, moisture) >= ros(wind, moisture) - 1e-9
    assert ros(wind, min(moisture + 0.01, 0.35)) <= ros(wind, moisture) + 1e-9

# 2. Directed walk costs: forward and reverse of the same edge differ only by the slope term (Session 22's DiGraph finding)
@given(slope=st.floats(-0.6, 0.6), length=st.floats(1, 500))
def test_slope_asymmetry_sign(slope, length):
    from wildfireguardian.routing import time_min
    fwd, rev = time_min(length, slope), time_min(length, -slope)
    assert (fwd >= rev) == (slope >= 0)

# 3. Time-expanded graph: a route that is safe at horizon h is still reported safe at any h' < h
@given(h=st.integers(1, 6))
def test_horizon_monotone(h): ...
```
Register `hypothesis` in `check_declared_deps.py`'s dev list so `make verify` stays green; set `@settings(deadline=None)` for anything touching rasterio.

### 2.8 Weekly literature routine (Semantic Scholar + arXiv)

Cloud routine, weekly, model Sonnet-class, **Custom** network: `api.semanticscholar.org`, `export.arxiv.org`, plus "include default list". No connectors except Gmail (for the digest). Seed file `docs/literature/seeds.json` with 5–10 positive paper IDs (the Korean fire-spread, Rothermel-vs-ML, evacuation-routing, LFMC papers already cited in `docs/MODEL_CARD.md`) and negatives (urban-traffic evacuation, pure remote-sensing detection).

Prompt core:
```
1. git checkout round3-dev.
2. POST https://api.semanticscholar.org/recommendations/v1/papers with docs/literature/seeds.json
   (fields=title,year,venue,abstract,externalIds,citationCount; limit=40). Sleep 1 s between calls.
3. GET http://export.arxiv.org/api/query?search_query=all:"wildfire spread" AND (all:evacuation OR all:"gradient boosting")&sortBy=submittedDate&max_results=30
4. Write docs/literature/YYYY-WW.md: for each paper, one line: relevance to WildfireGuardian (spread model / routing / vulnerability / none), and whether it changes any claim in docs/MODEL_CARD.md. Never edit MODEL_CARD.md itself.
5. Open a PR into round3-dev titled "lit: week YYYY-WW"; label kind/paper.
6. Send a 10-line digest with the PR link via the Gmail connector to siyeong0318@gmail.com.
```
Free Semantic Scholar key (form on their site) lifts the shared pool to 1 rps; store it as an environment **API credential** for host `api.semanticscholar.org`, not an env var.

## 3. Claude Code routines vs GitHub Actions cron — where each belongs

| | Cloud routine | GitHub Actions `schedule` |
|---|---|---|
| Min interval | 1 h (hard) | 5 min nominal; real delays 5–30 min under load |
| Billing | Subscription usage + daily run cap | Free/unlimited on public repo; Claude inside it via OAuth token = subscription usage |
| Auth to Claude | Built in (claude.ai login) | Secret `CLAUDE_CODE_OAUTH_TOKEN` |
| Repo state | Fresh clone of default branch; push only to `claude/*` | Checkout any ref; push wherever the token allows (dangerous with "never push Main") |
| Network | HTTP(S) via proxy; Trusted allowlist; Custom for FIRMS/S2/arXiv | Open internet |
| MCP connectors | Yes (Gmail, Notion, etc.), writes without prompts | Only what you wire via `--mcp-config` |
| Dies after inactivity | No | Yes: public-repo schedules auto-disable after 60 days without a push (irrelevant while the routine is committing) |
| Tool access | Full Claude Code session, skills in repo, `gh` via proxy | Same action runtime, but plain-text `prompt` has no shell until `--allowedTools` grants it |
| Best for | The science/dev loop (re0-loop, nba, catchup), FIRMS polling with a Custom allowlist, literature digests | Deterministic gates (tests, `make verify`, Playwright), reacting to PR events, `@claude` interactivity |

Recommendation: **routines do the thinking, Actions do the checking.** Never have both edit the same branch. One exception worth a routine *and* an Action: a nightly `make verify` on `round3-dev` in Actions (deterministic, free) plus a weekly routine that reads the failure log and opens a fix PR.

Routine prompt hygiene that the docs make necessary: (1) first line `git checkout round3-dev` (default branch is `Main`); (2) treat the `<routine-fire-payload>` block as data; (3) end with a Gmail-connector digest; (4) "A green run status does not mean the task succeeded" — the prompt should write `docs/loop/RUN_<date>.md` so `catchup` has something to read next hour.

## 4. Email delivery — decision

1. **Now, zero config:** GitHub notification emails for PR opened / review posted / CI failed (repo owner is subscribed by default). Turn on "Actions: failed workflows only" in GitHub notification settings.
2. **Now, from routines:** the Gmail connector (already attached to this claude.ai account — this session exposes `send_message`/`create_draft` tools from it). Keep it as the *only* connector on the loop routines so a bad prompt cannot write to Notion/Airtable.
3. **Not possible:** SMTP from a routine (`delivery/email.py` uses `smtp.gmail.com:465`; the VM only has an HTTP/HTTPS proxy). `docs/delivery_channels.md` §3-B already records SMTP being blocked in an agent sandbox; the cloud VM is the same situation.
4. **Later, if GitHub mail is too noisy:** `dawidd6/action-send-mail@v3` with `server_address: smtp.gmail.com`, `server_port: 465`, `secure: true`, `username/password` from secrets (the app password the project already provisions for `delivery/email.py`). Only on `if: failure()`.
5. **No:** SendGrid (free tier gone). Resend/Brevo only as a fallback HTTP API from a routine with a Custom allowlist.

## 5. Later list (with the trigger that promotes each)

| Tool | Promote when | Snippet / note |
|---|---|---|
| `xu-cheng/latex-action@v4` | `paper/main.tex` exists | `- uses: xu-cheng/latex-action@v4` / `with: { root_file: paper/main.tex, working_directory: paper }` → upload `paper/main.pdf` artifact. IEEEtran ships with full TeX Live in the container. |
| Copilot Student code review | Student Pack verified | Repo → Settings → Rules → "Automatically request Copilot code review". 200 credits/mo covers ~a few dozen reviews. |
| Codex cloud auto-review | Only if a ChatGPT Plus sub already exists | Different model family = genuinely independent opinion; otherwise not worth $20/mo. |
| `@axe-core/playwright` | After 2.6 lands | `const r = await new AxeBuilder({page}).analyze(); expect(r.violations.filter(v=>['critical','serious'].includes(v.impact))).toEqual([])` |
| pandera | First schema bug in an OOF parquet / arm JSON | `DataFrameSchema` for `spread_v2_lofo_oof.parquet`; call from `verify_numbers.py`. |
| basedpyright | If the loop ever adds type hints to `src/` systematically | `basedpyright --level error src/` in CI, never on `scripts/`. |
| git-cliff | Finals freeze tag | `orhun/git-cliff-action@v4` → `CHANGELOG.md`; needs conventional commits from the loop (`re0-git`). |
| codecov | Judges/reviewers ask for coverage | `pytest --cov=wildfireguardian --cov-report=xml` + `codecov/codecov-action@v5` with `token: ${{ secrets.CODECOV_TOKEN }}`. |
| DVC + Google Drive remote | A collaborator needs `data/raw` | `dvc init; dvc remote add -d gdrive gdrive://<folder>; dvc add data/raw/firms_data` — keeps the `.gitignore` rules intact. |
| Dependabot for Python | Never for pins that are scientific constraints; maybe for `fastapi/uvicorn/httpx` only | Separate `pip` entry with `allow: [{dependency-name: fastapi}, ...]`. |
| anthropics/skills `docx` | When 서식/KCF documents are regenerated in-loop | Already present as `anthropic-skills:docx` in this session. |

## 6. Do-not list (reasons)

- **lakeFS, Great Expectations, MLflow, W&B** — platform-sized tools for a repo whose provenance (`snapshot_external.py` + `MANIFEST.json`), experiment registry (`NUMBERS.json`, `make verify`, `artifact_manifest.json`) and baseline freeze (`baseline_phase13.json`) already exist and work offline at the booth. Adding a cloud tracker would give judges a second, unverifiable source of numbers, which `check_number_collisions.py` exists to prevent.
- **semantic-release** — pushes tags/commits to the default branch automatically; violates `HANDOFF_ROUND3.md` §5.1. Nothing is published to PyPI.
- **SonarCloud, Cursor Bugbot, OpenHands review, Devin, Jules, Aider, SWE-agent** — either paid, or a second autonomous *editor* competing for the same branches, or generic smell reports. The project's failure modes are scientific (leakage, number drift, DEM lineage), which `mandela`, `factchk`, `check_arm_isolation.py` target and generic reviewers do not.
- **obra/superpowers** — duplicates paperthin + ponytail + systematic-debugging + verification-before-completion. paperthin's own README: "Most agent skills are slop."
- **GitHub Projects** — GraphQL-only; blocked by the cloud proxy; Issues + labels are enough.
- **Overleaf git sync** — paid; the repo + latex-action is the source of truth.
- **marp/reveal.js, Lighthouse** — wrong deliverable (booth page, offline).
- **Papers with Code** — defunct since 2025-07-24. **SendGrid** — free tier ended 2025-05-27.
- **Elicit/Consensus/NotebookLM as loop components** — no automatable free API; fine for the student's own reading.
- **pyright now** — untyped 115-script tree; the loop would drown in type noise before the finals.
- **Renovate, DVC now, Dependabot on Python pins** — `osmnx==2.0.7` and friends are recorded scientific constraints; a bot that floats them silently re-runs the Round-2 environment failure.

## 7. Risks the tooling does not fix

- KCF rule that finals work must not contradict the submitted 서식1/서식2 purpose: none of the above changes purpose; the literature routine must not rewrite `MODEL_CARD.md` (prompt says so).
- Subscription burn: two routines (hourly dev loop + weekly literature) plus PR reviews on every push can exhaust a Pro plan's daily cap; watch `claude.ai/code/routines`. Skip-draft rules and `--max-turns` are the levers.
- The first CI run will surface pins that exist on conda-forge but not PyPI (UNVERIFIED that all 20 pins resolve on x86_64 wheels; Session 18 covered aarch64). If one fails, that is itself a `docs/ENVIRONMENT.md` finding.
- `no-commit-to-branch Main` in pre-commit protects the laptop; it does nothing in the cloud (routines cannot push to protected branches anyway; the user should protect `Main` in GitHub settings).

## Sources

- https://code.claude.com/docs/en/routines
- https://code.claude.com/docs/en/scheduled-tasks
- https://code.claude.com/docs/en/cloud-environments
- https://code.claude.com/docs/en/claude-code-on-the-web
- https://code.claude.com/docs/en/github-actions
- https://code.claude.com/docs/en/code-review
- https://github.com/anthropics/claude-code-action
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/billing/managing-billing-for-your-products/about-billing-for-github-actions
- https://github.com/orgs/community/discussions/185355 (60-day schedule auto-disable)
- https://github.com/astral-sh/ruff-pre-commit (rev v0.16.5)
- https://github.com/astral-sh/setup-uv ; https://docs.astral.sh/uv/guides/integration/github/
- https://github.com/kynan/nbstripout
- https://github.com/RobertCraigie/pyright-python ; https://docs.basedpyright.com/
- https://hypothesis.readthedocs.io/
- https://pytest-xdist.readthedocs.io/en/latest/distribution.html
- https://github.com/unionai-oss/pandera/discussions/598 ; https://aeturrell.com/blog/posts/the-data-validation-landscape-in-2025/
- https://doc.dvc.org/user-guide/data-management/remote-storage/google-drive ; https://lakefs.io/blog/dvc-vs-git-vs-dolt-vs-lakefs/
- https://github.com/codecov/codecov-action
- https://github.com/marketplace/sonarcloud
- https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-automatic-review ; https://github.blog/changelog/2026-04-27-github-copilot-code-review-will-start-consuming-github-actions-minutes-on-june-1-2026/ ; https://codehelper.me/articles/github-student-pack/ (Copilot Student plan, 2026-03-12)
- https://developers.openai.com/codex/integrations/github ; https://developers.openai.com/codex/pricing
- https://gitautoreview.com/compare/cursor-bugbot-alternative ; https://omidsaffari.com/blog/devin-pricing ; https://hackup.ai/ai-plans/jules/
- https://github.com/marketplace/actions/openhands-pr-review-action ; https://docs.openhands.dev/sdk/guides/github-workflows/pr-review
- https://github.com/SWE-agent/SWE-agent ; https://github.com/SWE-agent/mini-swe-agent
- https://aider.chat/docs/
- https://github.com/obra/superpowers-skills ; https://github.com/anthropics/skills
- https://hyper.ai/en/news/42900 (Papers with Code shutdown 2025-07-24)
- https://api.semanticscholar.org/api-docs/recommendations ; https://www.semanticscholar.org/product/api/tutorial
- https://github.com/TideDra/zotero-arxiv-daily
- https://help.zenodo.org/docs/github/ ; https://citation-file-format.github.io/
- https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration
- https://github.com/xu-cheng/latex-action (v4)
- https://github.com/KoharaKazuya/marp-cli-action
- https://testdino.com/blog/playwright-visual-testing ; https://dev.to/zoetaka38/why-your-playwright-screenshots-show-for-japanese-chinese-korean-text-and-the-3-line-15pj
- https://github.com/treosh/lighthouse-ci-action ; https://www.checklyhq.com/blog/integrating-accessibility-checks-in-playwright-tes/
- https://0x5.uk/2026/03/12/automatic-release-notes-with-semantic-commits-and-git-cliff/ ; https://github.com/semantic-release/semantic-release
- https://github.com/dawidd6/action-send-mail
- https://blog.mystrika.com/sendgrid-free-tier/ (SendGrid free plan retired 2025-05-27)
- https://paperguide.ai/blog/consensus-vs-notebooklm/ ; https://thedrive.ai/blog/elicit-vs-consensus-ai-research-tools
- https://konvu.com/compare/dependabot-vs-renovate
- Local: `docs/HANDOFF_ROUND3.md` §5, `docs/ENVIRONMENT.md`, `requirements.txt`, `Makefile`, `docs/SESSION22_REPORT.md`, `docs/delivery_channels.md`, `.claude/settings.json`, paperthin `README.md`.
