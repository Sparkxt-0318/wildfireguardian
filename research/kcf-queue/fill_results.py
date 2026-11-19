"""RESULTS.template.md + results/oat.json -> RESULTS.md (the only edit is the one-at-a-time table)."""
import json
t = open("RESULTS.template.md").read()
o = json.load(open("results/oat.json"))
names = {"OAT_hh_low": "households × 0.7", "OAT_hh_high": "households × 1.4", "OAT_vph_low": "0.9 vehicles/household", "OAT_vph_high": "1.5 vehicles/household",
         "OAT_W_low": "spread 15 min", "OAT_W_high": "spread 60 min", "OAT_rho_low": "smoke factor 1.00", "OAT_rho_high": "smoke factor 0.70",
         "OAT_cap_other_low": "other roads 1,000 veh/h", "OAT_cap_other_high": "other roads 600 veh/h"}
lines = ["| one parameter changed from middle | " + " | ".join(o.keys()) + " |", "|---|" + "---|" * len(o)]
def cell(c, k):
    r = o[c].get(k)
    if r is None: return "not finished"
    return "%d clear / %d cannot; median shift %s min; max shift %s; max queue delay %s min" % (r["clear"], r["cannot_clear"], r["median_shift_vs_L0_min"], r["max_shift_vs_L0_min"], r["max_queue_effect_min"])
for k in ["MID"] + list(names):
    lines.append("| %s | %s |" % ("middle (reference)" if k == "MID" else names[k], " | ".join(cell(c, k) for c in o)))
lines.append("")
lines.append("Shift = leave-by earlier than the card's free-flow figure `L0`; the median equals the spread. Queue delay = free flow with the same spread minus the solved start. "
             "Parameter names in `results/oat.json` follow the stress end (`high` = adverse), not the numeric value.")
open("RESULTS.md", "w").write(t.replace("<!--OAT-->", "\n".join(lines)))
print("written")
