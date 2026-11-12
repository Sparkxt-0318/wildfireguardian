#!/bin/sh
# Runs every tests/*.wfgc through the checker. Expected verdict = filename prefix
# (accept_* -> ACCEPT, exit 0; reject_* -> REJECT, exit 1). Usage: run_tests.sh [checker]
DIR=$(dirname "$0")
# default: the binary next to this tests/ directory, so the script works from any working directory (Nora C3 note)
CHECK=${1:-"$DIR/../wfgc_check"}
fail=0; n=0
for f in "$DIR"/*.wfgc; do
  n=$((n+1))
  base=$(basename "$f")
  case "$base" in
    accept_*) want=ACCEPT; wcode=0 ;;
    reject_*) want=REJECT; wcode=1 ;;
    *) echo "BAD-NAME $base"; fail=1; continue ;;
  esac
  out=$("$CHECK" "$f"); code=$?
  lines=$(printf '%s\n' "$out" | wc -l)
  got=${out%% *}
  if [ "$got" = "$want" ] && [ "$code" -eq "$wcode" ] && [ "$lines" -eq 1 ]; then
    echo "ok    $base: $out"
  else
    echo "FAIL  $base: got '$out' exit $code, want $want exit $wcode"; fail=1
  fi
done
# stdin path must give the same answer
out=$("$CHECK" - < "$DIR/accept_route_wait.wfgc"); code=$?
if [ "$out" = "ACCEPT ROUTE 7" ] && [ $code -eq 0 ]; then echo "ok    stdin: $out"; else echo "FAIL  stdin: '$out' $code"; fail=1; fi
# unreadable input -> exit 2
out=$("$CHECK" "$DIR/does_not_exist.wfgc"); code=$?
if [ "${out%% *}" = "REJECT" ] && [ $code -eq 2 ]; then echo "ok    unreadable: $out (exit 2)"; else echo "FAIL  unreadable: '$out' $code"; fail=1; fi
if [ $fail -ne 0 ]; then echo "TESTS FAILED"; exit 1; fi
echo "ALL $n FILE TESTS + 2 EXTRA PASSED"
