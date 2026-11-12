#!/usr/bin/env bash
# FDYN_PLAN.md memory-guard repeat: every 300 s / 900 s request stopped on the 3,072 MiB guard, so each budget is
# repeated once with the guard at 12,288 MiB (non-evaluated, labelled). Detached; waits for chain_rest.sh to finish.
set -u
S=/tmp/claude-0/-home-user-wildfireguardian/a8e57cff-dd1e-5372-8b6a-c73e09beb008/scratchpad
R=/home/user/wildfireguardian
P=$R/research/harness-2026-11/F-3.4
ST=$S/CHAIN_STATUS
cd "$R"
mark() { echo "$(date -u +%FT%TZ) $*" >> "$ST"; }
until grep -q CHAIN_DONE "$ST"; do sleep 15; done
mark "g12k chain started"
for b in 300 900; do
  .venv/bin/python $P/fdyn_profile.py --kit $S/window-kit --leo $S/fdyn/leo --out $S/fdyn_b${b}_g12k --budget $b \
    --memory-guard-mib 12288 > $S/fdyn_b${b}_g12k.log 2>&1; mark "fdyn_b${b}_g12k rc=$?"
done
mark "G12K_DONE"
