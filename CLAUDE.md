## ui-ux-pro-max-skill scoping (operator console only)
When using the ui-ux-pro-max skill for the operator console dashboard,
restrict queries to: "Data-Dense Dashboard", "Real-Time Monitoring",
"Executive Dashboard" categories, plus its accessibility/UX-anti-pattern
checklist. Do NOT use its consumer/SaaS/spa/e-commerce style categories
(glassmorphism, neubrutalism, vaporwave, etc.) on this project. This is
a life-safety rescue-dispatch tool, not a marketing product — legibility
and WCAG AA contrast take priority over visual polish.

## Autonomous loop (from 2026-09-03)
Every agent session in this repository, cloud routine or local, reads
`docs/auto/CHARTER.md` before doing anything else. It fixes the branch
(`auto/dev`, never `Main`), the lap protocol, the gates that must be green
before a push (`python scripts/auto/gates.py --mode full`), the backlog
(`docs/auto/BACKLOG.md`), the escalation ledger (`docs/auto/NEEDS_HUMAN.md`)
and the 24 rules of `docs/HANDOFF_ROUND3.md` §5 that the loop must never break.
Bootstrap a fresh checkout with `bash scripts/auto/bootstrap.sh`.
