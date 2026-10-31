# Source and clock admission repair after independent review

The independent review of fd8bf2e78532b76d2dd2cfd094d3499def90fc23 found three
tiny API defects that the original fixtures missed. Its original receipt and
fixture file are retained unchanged. This repair narrows supported inputs;
the native timed contact/K campaign remains closed pending independent recheck.

The initial source constructor could discard contradictory known active fire
by intersecting it with known burned support. It now preserves the canonical
cutoff-field invariants before that intersection: known activity requires
known burned support; active remaining duration is positive; inactive remaining
duration is zero; finite negative remaining values are refused even when the
initial-activity mask is invalid. Consumed cutoff fields must have floating
dtypes, validity masks remain genuinely Boolean and affine input has exactly
six floating entries. The canonical comparison is unchanged
integration/src/wfg_latest/contract.py::validate_raw, lines 185-241. The existing
exact T upper bound remains stricter than that validator's relative tolerance.
No unknown cell is filled, and valid unknown initial age still uses the full-T
enclosure. Valid unknown off-road source data remains stored and can coexist
with a supported local contact journey.

Member-validity bounds must now be positive whole seconds inside the saved
whole-second source horizon. A fractional bound is explicitly unsupported at
source admission. The planner no longer silently floors an accepted bound.
Inclusive terminal support still allows fractional dwell and checks its exact
represented rational finish against the integer bound. For exclusive terminal
support, dwell must be whole seconds. Under that admitted contract every full
journey finish is an integer, so finish < H is equivalent to finish <= H-1;
the existing one-second reduction therefore solves the same declared problem.
The independent raw checker enforces the same source/request admission rules.
Fractional dwell with an exclusive terminal is unresolved, with no optimum
claim, rather than being silently changed to a more restrictive finish problem.

UTC clock binding accepts RFC3339 date/time with explicit seconds, up to six
fractional second digits, and either Z or a numeric HH:MM offset. Higher
precision and fractional offset-second syntax are refused before calling
datetime.fromisoformat, which would otherwise silently discard precision.
Accepted clocks normalize to UTC exactly at microsecond precision. Equivalent
offset representations pass; distinct microseconds fail binding. UTC datetime
objects are compared directly, with no epoch-float conversion, including the
year-9999 differing-microsecond and equivalent-offset controls. The fixed
native whole-second source timestamps require no change.

The new boundary tests compare source refusals and valid controls with the
unchanged canonical contract, retain the known-current and unknown-age cases,
reproduce the fractional-support two-destination counterexample as an admission
refusal, test inclusive fractional and exclusive integer dwell controls, and
test nanosecond rejection and exact offset/microsecond binding. Counts and
commands are in research/sipp-routing/KNOWN_FOOTPRINT_ADAPTER_REPAIR_RECEIPT.json.
That receipt also preserves the original fixture/producer/receipt and earlier
source/census evidence. This is software boundary evidence, without new native
arrays, trajectories, routing timing, thermal-policy, risk or physical evidence.
