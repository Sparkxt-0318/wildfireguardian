#!/usr/bin/env bash
# Sequential quiet-host chain for F-3.4 (detached; survives tool time limits). Usage: chain_rest.sh WAIT_PID
# Waits for the running cold-81 profile process to exit, then runs every later step; markers go to CHAIN_STATUS.
set -u
S=/tmp/claude-0/-home-user-wildfireguardian/a8e57cff-dd1e-5372-8b6a-c73e09beb008/scratchpad
R=/home/user/wildfireguardian
P=$R/research/harness-2026-11/F-3.4
ST=$S/CHAIN_STATUS
cd "$R"
mark() { echo "$(date -u +%FT%TZ) $*" >> "$ST"; }
mark "chain started; waiting for pid ${1:-none}"
if [ -n "${1:-}" ]; then while kill -0 "$1" 2>/dev/null; do sleep 15; done; fi
mark "cold81 finished"
.venv/bin/python $P/run_profile.py --kit $S/window-kit --out $S/clean_warm81b --reps 5 --budget 81 --warm > $S/clean_warm81b.log 2>&1; mark "warm81 rc=$?"
.venv/bin/python $P/run_profile.py --kit $S/window-kit --out $S/clean_cold30b --reps 2 --budget 30 > $S/clean_cold30b.log 2>&1; mark "cold30 rc=$?"
.venv/bin/python $P/run_profile.py --kit $S/window-kit --out $S/clean_plain81b --reps 2 --budget 81 --mode plain > $S/clean_plain81b.log 2>&1; mark "plain81 rc=$?"
.venv/bin/python $P/run_profile.py --kit $S/snap10-kit --out $S/snap10_plain81 --reps 2 --budget 81 --mode plain > $S/snap10_plain81.log 2>&1; mark "snap10 rc=$?"
.venv/bin/python $P/run_profile.py --kit $S/snap6-kit --out $S/snap6_plain81 --reps 1 --budget 81 --mode plain > $S/snap6_plain81.log 2>&1; mark "snap6 rc=$?"
bash $P/fdyn_prepare.sh $S/fdyn/leo $S/venv-fdyn/bin/python > $S/fdyn_prepare.log 2>&1; rc=$?; mark "fdyn_prepare rc=$rc"
if [ $rc -eq 0 ]; then
  for b in 30 300 900; do
    .venv/bin/python $P/fdyn_profile.py --kit $S/window-kit --leo $S/fdyn/leo --out $S/fdyn_b$b --budget $b > $S/fdyn_b$b.log 2>&1; mark "fdyn_b$b rc=$?"
  done
fi
mark "CHAIN_DONE"
