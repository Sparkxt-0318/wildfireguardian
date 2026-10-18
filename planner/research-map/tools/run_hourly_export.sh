#!/usr/bin/env bash
# WildfireGuardian — 시간별 누적 연소 확률(F(h)) 내보내기 · KFS_01 의성·안동 2025
# Hourly cumulative burn-probability export for the layer viewer. One file; run it from anywhere:
#
#     bash run_hourly_export.sh
#
# It finds (or clones) the repository's Main branch, finds the KFS_01 environmental inputs,
# sets up Python 3.12 + the pinned forecast package, and runs the recursive Monte Carlo rollout
# (model.predict_cumulative) with the published c651 checkpoint. Nothing is retrained or modified.
#
# Options:  --repo DIR      checkout containing forecast/ (default: search, else clone Main)
#           --data DIR      environment data root holding events.json and regions/KFS_01/
#           --samples N     Monte Carlo trajectories (default 1024)
#           --hours H       horizons 1..H (default 12)
#           --env recorded|persist   later-hour inputs (default recorded)
#           --every N       run every N hours across 03-23 10:00 – 03-26 17:00 KST instead of the 3 recorded input times
#           --out FILE      output (default ./kfs01_hourly.npz)
set -euo pipefail
REPO="${WFG_REPO:-}"; DATA="${WFG_DATA_ROOT:-}"; OUT="$PWD/kfs01_hourly.npz"; EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --data) DATA="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    --samples|--hours|--env|--seed|--device|--every) EXTRA+=("$1" "$2"); shift 2;;
    -h|--help) sed -n 2,20p "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
say() { printf '\n==> %s\n' "$*"; }
die() { printf '\n[중단 / stopped] %s\n' "$*" >&2; exit 1; }
CKPT_REL="forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
is_repo() { [ -f "$1/forecast/pyproject.toml" ] && [ -f "$1/forecast/wildfire/cumulative.py" ] && [ -f "$1/$CKPT_REL" ]; }
is_data() { [ -f "$1/events.json" ] && [ -f "$1/biome_classes.json" ] && [ -f "$1/regions/KFS_01/arrival_time_hours.tif" ] && [ -d "$1/regions/KFS_01/weather" ]; }

# 1. repository (Main branch, with forecast/ and the c651 checkpoint) ---------------------------
if [ -n "$REPO" ]; then is_repo "$REPO" || die "--repo $REPO has no forecast/ package from the Main branch (needs forecast/wildfire/cumulative.py)."; fi
if [ -z "$REPO" ]; then
  for c in "$PWD" "$PWD/.." "$HOME/wildfireguardian" "$HOME/Documents/wildfireguardian" "$HOME/Desktop/wildfireguardian" \
           "$HOME/Developer/wildfireguardian" "$HOME/code/wildfireguardian" "$HOME/Projects/wildfireguardian" "$HOME/GitHub/wildfireguardian" \
           "$HOME/wildfireguardian-forecast"; do
    if is_repo "$c"; then REPO="$(cd "$c" && pwd)"; break; fi
  done
fi
if [ -z "$REPO" ]; then
  f="$(find "$HOME" -maxdepth 6 \( -path "$HOME/Library" -o -name .Trash -o -name node_modules -o -name .venv \) -prune -o -type f -path '*/forecast/wildfire/cumulative.py' -print 2>/dev/null | head -1 || true)"
  if [ -n "$f" ]; then c="$(cd "$(dirname "$f")/../.." && pwd)"; is_repo "$c" && REPO="$c"; fi
fi
if [ -z "$REPO" ]; then
  REPO="$HOME/wildfireguardian-forecast"
  say "Cloning the Main branch into $REPO (your other checkouts are not touched)"
  command -v git >/dev/null || die "git is not installed. Run: xcode-select --install"
  git clone --depth 1 --branch Main https://github.com/Sparkxt-0318/wildfireguardian.git "$REPO"
  is_repo "$REPO" || die "The clone has no forecast/ package; check https://github.com/Sparkxt-0318/wildfireguardian/tree/Main/forecast"
fi
say "Repository: $REPO"

# 2. KFS_01 environmental inputs (not on GitHub: forecast/README.md, External inputs) ---------------
if [ -n "$DATA" ] && ! is_data "$DATA"; then
  for sub in environment data/environment wildfire/data/environment; do if is_data "$DATA/$sub"; then DATA="$DATA/$sub"; break; fi; done
  is_data "$DATA" || die "--data $DATA does not contain events.json, biome_classes.json and regions/KFS_01/ (with weather/)."
fi
if [ -z "$DATA" ]; then
  for c in "$REPO/forecast/data/environment" "$REPO/data/environment"; do if is_data "$c"; then DATA="$c"; break; fi; done
fi
if [ -z "$DATA" ]; then
  say "Searching your home folder and external drives for the KFS_01 inputs (can take a minute)…"
  while IFS= read -r f; do
    c="$(cd "$(dirname "$f")/../.." && pwd)"
    if is_data "$c"; then DATA="$c"; break; fi
  done < <(find "$HOME" /Volumes -maxdepth 9 \( -path "$HOME/Library" -o -name .Trash -o -name node_modules -o -name .venv -o -name .git \) -prune -o \
             -type f -name arrival_time_hours.tif -path '*/regions/KFS_01/*' -print 2>/dev/null || true)
fi
if [ -z "$DATA" ]; then
  say "Looking for the original forecast workspace archive (e.g. 'wildfire 3 (1).zip')…"
  while IFS= read -r z; do
    entry="$(unzip -Z1 "$z" 2>/dev/null | grep -E '(^|/)regions/KFS_01/arrival_time_hours\.tif$' | head -1 || true)"
    [ -n "$entry" ] || continue
    prefix="${entry%regions/KFS_01/arrival_time_hours.tif}"
    dest="$HOME/wildfireguardian-forecast-data"
    say "Extracting only KFS_01 inputs from: $z"
    mkdir -p "$dest"
    unzip -Z1 "$z" | awk -v p="$prefix" 'index($0, p) == 1 { r = substr($0, length(p) + 1); if (r != "" && index(r, "/") == 0) print }' > "$dest/.rootfiles"
    unzip -q -o "$z" "${prefix}regions/KFS_01/*" -d "$dest"
    while IFS= read -r rf; do unzip -q -o "$z" "$rf" -d "$dest"; done < "$dest/.rootfiles"
    unzip -q -o "$z" "${prefix}quality_flags/KFS_01/*" -d "$dest" 2>/dev/null || true
    if is_data "$dest/$prefix"; then DATA="$(cd "$dest/$prefix" && pwd)"; break; fi
  done < <(find "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents" /Volumes -maxdepth 4 -type f -iname '*.zip' -size +20M 2>/dev/null || true)
fi
if [ -z "$DATA" ]; then
  die "KFS_01 환경 입력 데이터를 찾지 못했습니다.
  The forecast needs the aligned environmental rasters, which are not published on GitHub
  (forecast/README.md, External inputs). They are in the original forecast workspace archive
  (wildfire/data/environment, with events.json and regions/KFS_01/). If you know where it is:

      bash $0 --data \"/path/to/environment\"
"
fi
say "Inputs: $DATA"

# 3. Python 3.12 environment with the pinned forecast package -----------------------------------
VENV="$REPO/forecast/.venv"
ok_env() { [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 12); import torch, rasterio, wildfire.cumulative' >/dev/null 2>&1; }
if ! ok_env; then
  if command -v uv >/dev/null 2>&1 || [ -x "$HOME/.local/bin/uv" ]; then UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
  elif PY312="$(command -v python3.12 || ls /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 2>/dev/null | head -1)" && [ -n "$PY312" ]; then UV=""
  else
    say "Installing uv (a Python installer) to get Python 3.12"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV="$HOME/.local/bin/uv"; [ -x "$UV" ] || UV="$(command -v uv || true)"; [ -n "$UV" ] || die "uv installation failed; install Python 3.12 (brew install python@3.12) and rerun."
  fi
  say "Creating $VENV (Python 3.12) and installing the forecast package (PyTorch 2.5.1 etc.; first run takes a few minutes)"
  rm -rf "$VENV"
  if [ -n "$UV" ]; then
    "$UV" venv --python 3.12 "$VENV"
    "$UV" pip install --python "$VENV/bin/python" -e "$REPO/forecast"
  else
    "$PY312" -m venv "$VENV"
    "$VENV/bin/python" -m pip install --upgrade pip
    "$VENV/bin/python" -m pip install -e "$REPO/forecast"
  fi
  ok_env || die "The forecast package did not import; see the messages above."
fi
"$VENV/bin/python" -c 'import sys, torch; print("python", sys.version.split()[0], "torch", torch.__version__)'

# 4. run --------------------------------------------------------------------------------------------
TMPD="$(mktemp -d)"; trap 'rm -rf "$TMPD"' EXIT
cat > "$TMPD/export_hourly_cumulative.py" <<'PYEOF'
#!/usr/bin/env python3
"""Export hourly cumulative new-burn probability for the layer viewer (KFS_01, 의성·안동 2025).

Runs the forecast package's recursive Monte Carlo rollout (`model.predict_cumulative`,
method="recursive") with the maintained checkpoint (c651…, mixed 3/5/7/9) at each recorded
input time, for horizons 1..H hours, and saves per-hour cumulative probability F(h), total
burned probability, Monte Carlo standard error and validity on the native 375 m event grid.

Nothing is retrained and no forecasting code is modified; this only calls the public API.
It needs the aligned environmental data tree that is not published on GitHub
(forecast/README.md, "External inputs"). Run it where that tree exists:

    cd forecast
    .venv/bin/python /path/to/export_hourly_cumulative.py --data-root data/environment --out kfs01_hourly.npz

Environment for later hours (--env):
  recorded  (default) slice k of `environmental_forecast` is the recorded snapshot at t+k h,
            i.e. a retrospective run with the hourly inputs that were later recorded.
  persist   no environmental_forecast; the cutoff conditions repeat every hour (API default).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

CUTOFFS = ("2025-03-23T01:00:00Z", "2025-03-24T09:00:00Z", "2025-03-25T17:00:00Z")
EXPECTED_CHECKPOINT_PREFIX = "c651f6724fe6b036"


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_numpy(x):
    try:
        import torch
        if isinstance(x, torch.Tensor):
            return x.detach().cpu().numpy()
    except ImportError:
        pass
    return np.asarray(x)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", default=None, help="aligned environmental data root (default: forecast/data/environment)")
    ap.add_argument("--event", default="KFS_01")
    ap.add_argument("--cutoffs", nargs="+", default=list(CUTOFFS))
    ap.add_argument("--every", type=int, default=0,
                    help="instead of --cutoffs: every N hours from 2025-03-23T01:00Z to 2025-03-26T08:00Z (skips times without inputs)")
    ap.add_argument("--hours", type=int, default=12)
    ap.add_argument("--samples", type=int, default=1024, help="Monte Carlo trajectories (n_samples)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch", type=int, default=32, help="trajectory_batch_size")
    ap.add_argument("--env", choices=("recorded", "persist"), default="recorded")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--allow-other-checkpoint", action="store_true")
    ap.add_argument("--out", default="kfs01_hourly.npz")
    a = ap.parse_args(argv)

    from wildfire import load_data, load_model, select_time, available_cutoffs
    from wildfire.paths import DEFAULT_CHECKPOINT, DATA_ROOT
    from wildfire.schema import TRAINING_SOURCE_CHANNELS

    root = Path(a.data_root) if a.data_root else Path(DATA_ROOT)
    ckpt = Path(DEFAULT_CHECKPOINT)
    ck_sha = sha256(ckpt)
    if not ck_sha.startswith(EXPECTED_CHECKPOINT_PREFIX) and not a.allow_other_checkpoint:
        print(f"checkpoint {ckpt} is {ck_sha[:16]}, not c651; pass --allow-other-checkpoint to continue", file=sys.stderr)
        return 2
    H = a.hours
    need = H if a.env == "recorded" else 1
    ok = set(available_cutoffs(a.event, data_root=root, sequence_length=need))
    if a.every > 0:
        start = datetime(2025, 3, 23, 1, tzinfo=timezone.utc)
        grid = [iso(start + timedelta(hours=h)) for h in range(0, 80, a.every)]
        a.cutoffs = [c for c in grid if c in ok]
        print(f"{len(a.cutoffs)} cutoffs every {a.every} h ({len(grid) - len(a.cutoffs)} skipped without a complete {need}-hour input window)")
    for c in a.cutoffs:
        if c not in ok:
            print(f"cutoff {c} has no complete {need}-hour input window for {a.event} under {root}", file=sys.stderr)
            return 2

    model = load_model(device=a.device)
    out: dict[str, np.ndarray] = {}
    meta = dict(event=a.event, cutoffs=a.cutoffs, hours=list(range(1, H + 1)), n_samples=a.samples, seed=a.seed,
                trajectory_batch_size=a.batch, env=a.env, method="recursive", boundary="zero",
                missing_burned_area="unburned", checkpoint=str(ckpt), checkpoint_sha256=ck_sha,
                data_root=str(root), generated_at=iso(datetime.now(timezone.utc)), runs=[])
    with load_data(root, events=[a.event], channels=TRAINING_SOURCE_CHANNELS,
                   sequence_length=None, patch_size=None) as data:
        if len(data) != 1:
            print(f"expected one full-rectangle sample for {a.event}, got {len(data)}", file=sys.stderr)
            return 2
        timeline = data[0]
    for k, c in enumerate(a.cutoffs):
        t0 = datetime.strptime(c, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        sample = select_time(timeline, c)
        kw = dict(hours=list(range(1, H + 1)), method="recursive", n_samples=a.samples, seed=a.seed,
                  trajectory_batch_size=a.batch, boundary="zero", missing_burned_area="unburned")
        if a.env == "recorded":
            # slice 0 drives (t, t+1h] with the snapshot at t (as ordinary one-hour prediction does),
            # slice k drives (t+k, t+k+1] with the recorded snapshot at t+k.
            seq = select_time(timeline, c, iso(t0 + timedelta(hours=H - 1)))
            kw["environmental_forecast"] = {
                "features": seq["features"][:, None],
                "feature_valid": seq["feature_valid"][:, None],
                "channel_names": list(seq["channel_names"]),
            }
        started = time.time()
        res = model.predict_cumulative(sample, **kw)
        arr = res.numpy()
        secs = time.time() - started
        prob = to_numpy(arr["probability"]).reshape(H, *to_numpy(arr["probability"]).shape[-2:]).astype(np.float32)
        valid = to_numpy(arr["valid"]).reshape(prob.shape).astype(bool)
        se = to_numpy(arr["mc_standard_error"]).reshape(prob.shape).astype(np.float32)
        burned = to_numpy(arr.get("burned_probability", prob)).reshape(prob.shape).astype(np.float32)
        init = to_numpy(sample["burned_area"])[0, 0].astype(np.float32)
        out[f"c{k}_probability"] = prob
        out[f"c{k}_burned_probability"] = burned
        out[f"c{k}_mc_standard_error"] = se
        out[f"c{k}_valid"] = valid
        out[f"c{k}_initial_burned"] = init
        if k == 0:
            out["affine_transform"] = to_numpy(sample["affine_transform"]).astype(np.float64)
            out["epsg"] = np.array(int(to_numpy(sample["epsg"])))
        cells = valid.any(0).sum()
        exp_km2 = [float(np.nansum(np.where(valid[h], prob[h], 0)) * 0.140625) for h in range(H)]
        meta["runs"].append(dict(cutoff=c, seconds=round(secs, 1), valid_cells=int(cells), expected_new_km2=exp_km2,
                                 metadata=json.loads(str(arr["metadata_json"])) if "metadata_json" in arr else None))
        print(f"{c}: {secs:.0f}s, valid {cells} cells, expected new burn {exp_km2[0]:.2f} km² at 1 h → {exp_km2[-1]:.2f} km² at {H} h")
    out["meta_json"] = np.array(json.dumps(meta, ensure_ascii=False))
    np.savez_compressed(a.out, **out)
    print(f"wrote {a.out} ({Path(a.out).stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
PYEOF
say "Running the hourly Monte Carlo rollout (progress below)"
(cd "$REPO/forecast" && "$VENV/bin/python" -B "$TMPD/export_hourly_cumulative.py" --data-root "$DATA" --out "$OUT" ${EXTRA[@]+"${EXTRA[@]}"})
say "Done: $OUT
  Attach this file in the conversation (or push it to a branch) and it will be added to the map's hourly layer."
