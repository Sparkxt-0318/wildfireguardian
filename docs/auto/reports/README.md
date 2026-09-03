# Loop reports

One file per lap, written by `scripts/auto/report.py`: `<UTC stamp>-<kind>.md` where
kind is `dev` (a build lap), `critic` (the daily adversarial review), `research`
(the weekly literature scan), `red` (a lap whose gates failed; the work is parked on
`auto/red/<stamp>`), `kickoff` or `manual`. `docs/auto/STATE.json` points at the
latest. Reports carry no number that is not already in a committed artifact; the
`make verify` forbidden-string scan runs over this directory like any other.
