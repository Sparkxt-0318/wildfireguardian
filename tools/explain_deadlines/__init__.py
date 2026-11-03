"""Explainable leave-by deadlines for the planner's recorded scenarios (schema wfg.explanation/1).

Read-only with respect to routing, forecast and checking code: this package replays recorded checked routes against
the frozen hazard packets with the same contact rules the runtime checks use, and proves (or declines to explain) why
the next departure time has no checked route. See README.md.
"""
SCHEMA = "wfg.explanation/1"
VERSION = "1.1.0"
