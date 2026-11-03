"""Impact numbers from the recorded 2025 planner cache (MIT Solve 2027 application, work package P4).

Path A (this package, standard library only for the planner rules and max-flow) replicates the planner's own
definitions; path B (``wfg_impact.path_b``, pandas + networkx) recomputes every reported number independently.
All results are model-relative: they describe what the Route-Check API concluded for recorded fire-scenario members,
not evacuation outcomes.
"""
