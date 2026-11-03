"""Impact numbers from the recorded 2025 planner cache and this package's own road-graph values (MIT Solve 2027
application, work package P4).

Path A (this package, standard library only for the planner rules and max-flow) replicates the planner's own
definitions; path B (``wfg_impact.path_b``, pandas + networkx) recomputes every reported number independently.
All results are model-relative and come from two sources, flagged on every number in NUMBERS.json: Route-Check API
results recorded on the evaluated macOS arm64 host (planner cache), counted with the planner's rules together with
the planner's place files (``uses_graph`` false); and values this package computes itself from the SHA-verified road
graph and hazard packets (``uses_graph`` / ``uses_hazard`` true: fire-free trip times, the scenario-window
classification, road redundancy, route lengths), which are not Route-Check API results and not evaluated-host output
(the committed values were computed in a Linux container). None is an evacuation outcome.
"""
