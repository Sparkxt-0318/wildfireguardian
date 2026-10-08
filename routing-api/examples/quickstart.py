"""Run with an installed package from any working directory."""
import json
from wildfireguardian_routing import example, prepare_graph, solve, check_route

case = example()  # Small generated fixture, not a real fire.
prepared = prepare_graph(case["graph"])
result = solve(prepared, case["hazard"], case["request"])
print(json.dumps(result, indent=2))
if result.get("legs") is not None and result.get("destination") is not None:
    checked = check_route(case["graph"], case["hazard"], case["request"],
                          result["legs"], result["destination"])
    print("Independent route check:", checked["ok"])
