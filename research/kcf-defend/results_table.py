"""Per-hour summary table for RESULTS.md (primary configuration). Usage: python3 results_table.py RUNS_DIR"""
import sys
import pages as PG, aggregate as AG
J, R, M, stab, numbers = AG.main(sys.argv[1])
PG.LANG[0] = "en"
print("| Issue (KST) | ranked | rank 1 | person-min Δ30 / Δ60 / Δ120 | village-min Δ60 | villages helped Δ60 | distinct villages helped by top ten | top ten road / front | overlap with other arms (ORD, RUN, WORST, GUST, GUST_KMA) | stable |")
print("|---|---|---|---|---|---|---|---|---|---|")
for h in AG.HOURS:
    rk = R[("MEASURED", "8h", h, 60)]; C = M[("MEASURED", "8h", h)]
    if not rk:
        print(f"| {h+9:02d}:00 | 0 | – | | | | | | | |"); continue
    cid, B, U, n = rk[0]; e = C[cid]
    ll, nm, k, reg = PG.locate(cid, e); npl, dd = PG.nearest_place(ll)
    loc = f"{'front' if e['type']=='FRONT' else 'road'} near {PG.pname(npl['place_id'])} ({ll[1]:.3f} N, {ll[0]:.3f} E)"
    pm = " / ".join(f"{AG.score(e['gains'][D])[0]:,.0f}" for D in (30, 60, 120))
    helped = set(); types = [0, 0]
    for c, *_ in rk[:10]:
        helped |= set(C[c]["gains"][60]); types[C[c]["type"] == "FRONT"] += 1
    s = stab[h]; ov = ", ".join(str(s["overlap_8h_d60"][a]) for a in ["ORDINARY", "RUNNING", "WORST", "MEASURED_GUST", "MEASURED_GUST_KMA"])
    print(f"| {h+9:02d}:00 | {len(rk)} | {loc} | {pm} | {U:,.0f} | {n} | {len(helped)} | {types[0]} / {types[1]} | {ov} | {len(s['stable'])} |")
