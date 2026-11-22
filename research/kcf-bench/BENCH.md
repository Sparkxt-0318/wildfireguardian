# BENCH: time, memory and accuracy of four routing methods on one machine

Plan: `BENCH_PLAN.md` (committed before any timing, with amendments A1 to A3 listed at its end). Data: `results_hostB/`
(5 repeats, 240 timed tasks, no failures). Run 19 to 22 Nov 2026. Everything below is read from those files by `analyze.py`
and `accuracy.py`. All results are model-relative benchmark results, not a validation against real fires.

## Result in five lines

1. **Time against the old method.** Over all 9,722 recorded cases the old one-departure-at-a-time method takes about
   **43.6 h** cold (41.3 to 45.5 h) and **37.8 h** warm (35.1 to 39.9 h), scaled from 200 timed requests per cache. The deadline
   field answers the same cases in **20 minutes** (18 to 22). Ratio **129×** cold [114 to 151], **111×** warm [98 to 134]. Every
   new method is faster than the old one on every cache, cold and warm (72 of 72 comparisons; lowest lower bound 8.2×).
2. **Margins.** The margin field with ten margins (0 to 600 s) takes **15.4 minutes** for all six caches against 15.9 for the
   field at one margin without routes: **about the same time, 1.0× [0.9 to 1.2]**, so ten margins cost about what one does.
   **Where it is slower:** the margin field at one margin with routes takes 26.3 minutes against 20.3 for the field, so it is
   **slower than the field** (ratio 0.69 to 0.95; clearly below 1 on the three Yeongdeok caches and on UA 03-23 warm).
3. **Accuracy.** **Zero disagreements.** The field and the margin field at margin 0 match every one of the 11,283 requests the old
   method decided (all repeats, cold and warm), and each other on all 9,722 cases. 76,392 answers at ten margins and 8,488 at 60 s
   equal the existing field run on the widened instance. The old method left 717 of 12,000 requests unresolved (507 at its 30 s limit).
4. **Memory.** Peak resident memory: field 195 to 924 MB per whole-cache process, old method 302 to 1,278 MB (median) per request.
   **Where it is higher:** the field (535 MB) and the margin field at one margin (562 MB) use more than the old method's typical
   worker (302 MB) on UA 03-24, and the margin field at one margin is also higher on YD 03-26 (670 against 652). The decision-only
   versions (field and ten-margin field) are lower everywhere (189 to 423 MB).
5. **Conditions.** One machine class (Intel Xeon 2.10 GHz, 4 vCPU, Linux 6.18, Python 3.13.18), one pinned core, 5 repeats, cold and
   warm separate. The old method is scaled from a fixed random sample, not run on every case. The container restarted twice
   while this dataset was being collected; one old-method block straddled a restart.

## 1 Machine and conditions

| item | value |
|---|---|
| machine | Intel(R) Xeon(R) Processor @ 2.10GHz, 4 logical CPUs, 16 GiB, KVM virtual machine on a shared host |
| operating system | Linux 6.18.44-fc-v726 x86_64 (glibc 2.39) |
| language | CPython 3.13.18 (Clang 23.1.3), numpy 2.5.3; the margin field and the field are pure Python |
| code | working branch `claude/festive-curie-s8y4my`; run started at `05f3fc02`; margin field from `research/kcf-idea-routing` at `a471eee1`; harness files hashed in `results_hostB/machine.json` and unchanged during the run |
| threads | every timed process pinned to one core (`taskset -c 3`), one thread; the old method's worker processes inherit the pin |
| repeats and order | 5 repeats of every method on every cache, cold and warm separate; repeat-major order, caches rotated each repeat, method order reversed on even repeats |
| noise check | a fixed CPU probe before and after each of the 240 tasks: median 0.075 s, range 0.058 to 0.133 s; 12 tasks saw a reading above 0.10 s (listed by timestamp in the ledger) |
| other work | nothing else of this study ran while a timed task ran, except two short git operations (about 3 s and 1 s on other cores) logged in `results_hostB/EVENTS.md` |
| inputs | the six committed planner caches (checked against `planner/cache/INDEX.json`) and the SHA-verified routing release `research-final-20261015` |
| keys | none used. The folder "wildfire 3 (1)" was not reachable from the session; the repository was used instead |

An earlier machine (Intel Xeon 2.30 GHz, kernel v653) produced one partial repeat in `results/`. It is **not pooled** with the data below
(plan amendment A3). The session restarted eleven times on that machine (the last restart moved it to this one) and twice on this one; each restart is logged in the `EVENTS.md` of its folder.

## 2 Methods

* **OLD**: the finals-submission method. One departure, one request, the kit v3 worker (`RDA_CAND`) with its mandatory
  whole-road journey check, full policy, 30 s budget, 3,072 MiB guard, launched by the kit controller as the API does. Timed on a fixed random
  sample of 200 requests per cache (12,000 requests in total over 6 caches, 5 repeats and 2 modes; seed 20261119), then **scaled** to all cases of the cache (mean per request times
  the number of cases). Cold = the worker prepares the graph from scratch. Warm = the kit's own prepared-graph store.
* **FIELD**: the F-3.1 deadline field, unchanged: one backward field per destination, every case read off it, with an arrival from a witness route.
  **FIELD-D**: the same without the witness (decisions only).
* **MARGIN-1**: the margin field with M = 60 s, every case read at 60 s with a witness (compare with FIELD).
  **MARGIN-10**: one pass with M = 600 s, every case read at ten margins (0, 67, ..., 600 s), decisions only (compare with FIELD-D).
* Timed region for FIELD and MARGIN: instance construction, preconditions, the field pass and the read-off of every case, over **all** cases of the cache.
  Cold = first pass in a fresh process including loading the graph and packet; warm = second pass in the same process.

## 3 The table

Times are seconds. FIELD, FIELD-D and MARGIN rows are measured on **all** cases of the cache. OLD rows are scaled (see above); beside each is
the 95% interval of the sampling error over the 200 sampled requests, which is a different thing from the range over repeats. A ratio is the median over
repeats with the widest range the repeats allow, [minimum ÷ maximum, maximum ÷ minimum], followed by the plan's word: "faster" if the whole range is above 1,
"slower" if below, otherwise "not distinguished". The rows marked "sample" answer only the 200 sampled requests and are compared with the OLD time on those same requests (not scaled).
Peak MB is the process's peak resident memory (OLD: one worker, median per request; FIELD and MARGIN: the whole-cache process, with the memory
after loading in brackets). These are different units of work and are reported, not ranked.

| cache | method | cold s, median (range) | warm s, median (range) | OLD ÷ method, cold [range] | OLD ÷ method, warm [range] | FIELD ÷ MARGIN, cold [range] | FIELD ÷ MARGIN, warm [range] | peak MB | agreement |
|---|---|---|---|---|---|---|---|---|---|
| UA 0323 01Z | OLD (scaled) | 13461 (13066–15099); sampling 95% CI 13153–14413 | 11831 (11179–12209); sampling 95% CI 11086–12334 |  |  |  |  | 303 median, 413 max per request (one worker) | OLD unresolved (30 s budget) per 200: 0.0 cold, 0.0 warm |
| UA 0323 01Z | FIELD | 25.84 (21.87–30.35) | 25.40 (21.65–28.41) | 521 [430–690] faster | 466 [394–564] faster |  |  | 195 (baseline 129) | 200/200 vs OLD; 1523/1523 vs recorded |
| UA 0323 01Z | FIELD-D | 23.73 (20.68–27.60) | 22.20 (20.07–25.62) | 567 [473–730] faster | 533 [436–608] faster |  |  | 193 (baseline 129) | 200/200 vs OLD; 1523/1523 vs recorded |
| UA 0323 01Z | MARGIN-1 | 32.16 (28.21–35.56) | 32.41 (28.80–37.06) | 419 [367–535] faster | 365 [302–424] faster | 0.80 [0.62–1.08] not distinguished (vs FIELD) | 0.78 [0.58–0.99] slower (vs FIELD) | 220 (baseline 129) | 1470/1470 at m=60 vs widened FIELD |
| UA 0323 01Z | MARGIN-10 | 20.24 (18.73–23.33) | 19.26 (17.98–24.17) | 665 [560–806] faster | 614 [462–679] faster | 1.17 [0.89–1.47] not distinguished (vs FIELD-D) | 1.15 [0.83–1.42] not distinguished (vs FIELD-D) | 190 (baseline 129) | 200/200 vs OLD at 0; 1523/1523 vs FIELD at 0; 13230/13230 at m>0 vs widened FIELD |
| UA 0323 01Z | FIELD, sample specs only (OLD ÷ = on the same 200 requests, not scaled) | 19.53 (17.96–23.55) | 19.57 (17.49–23.28) | 90.50 [72.86–110] faster | 79.38 [63.06–91.68] faster |  |  | 195 (baseline 129) | timing row only |
| UA 0323 01Z | FIELD + route check, sample (OLD ÷ = on the same 200 requests, not scaled) | 69.36 (66.79–81.20) | 68.49 (63.86–76.97) | 25.48 [21.13–29.69] faster | 22.69 [19.07–25.11] faster |  |  | 197 (baseline 129) | 770 witness checks over all repeats, 0 failed |
| UA 0324 09Z | OLD (scaled) | 14185 (13420–14644); sampling 95% CI 13327–14666 | 12072 (11589–12784); sampling 95% CI 11481–12799 |  |  |  |  | 302 median, 421 max per request (one worker) | OLD unresolved (30 s budget) per 200: 2.0 cold, 2.0 warm |
| UA 0324 09Z | FIELD | 174 (166–185) | 176 (169–178) | 81.51 [72.43–87.96] faster | 68.69 [65.06–75.83] faster |  |  | 535 (baseline 133) | 198/198 vs OLD; 1512/1512 vs recorded |
| UA 0324 09Z | FIELD-D | 24.30 (21.99–24.44) | 23.46 (22.18–25.32) | 584 [549–666] faster | 515 [458–576] faster |  |  | 195 (baseline 133) | 198/198 vs OLD; 1512/1512 vs recorded |
| UA 0324 09Z | MARGIN-1 | 184 (174–187) | 186 (176–191) | 77.11 [71.96–84.32] faster | 64.96 [60.72–72.49] faster | 0.95 [0.89–1.07] not distinguished (vs FIELD) | 0.95 [0.88–1.01] not distinguished (vs FIELD) | 562 (baseline 133) | 1476/1476 at m=60 vs widened FIELD |
| UA 0324 09Z | MARGIN-10 | 20.32 (18.38–20.89) | 20.24 (19.24–21.77) | 698 [642–797] faster | 596 [532–664] faster | 1.20 [1.05–1.33] faster (vs FIELD-D) | 1.16 [1.02–1.32] faster (vs FIELD-D) | 196 (baseline 133) | 198/198 vs OLD at 0; 1518/1518 vs FIELD at 0; 13284/13284 at m>0 vs widened FIELD |
| UA 0324 09Z | FIELD, sample specs only (OLD ÷ = on the same 200 requests, not scaled) | 37.53 (35.27–38.93) | 36.54 (35.56–38.04) | 49.80 [45.41–54.71] faster | 43.53 [40.13–47.36] faster |  |  | 536 (baseline 133) | timing row only |
| UA 0324 09Z | FIELD + route check, sample (OLD ÷ = on the same 200 requests, not scaled) | 93.29 (89.31–97.82) | 93.29 (91.05–95.05) | 20.03 [18.07–21.60] faster | 17.05 [16.06–18.50] faster |  |  | 533 (baseline 133) | 795 witness checks over all repeats, 0 failed |
| UA 0325 17Z | OLD (scaled) | 24465 (21236–25485); sampling 95% CI 22465–25050 | 22468 (19634–23624); sampling 95% CI 20500–23136 |  |  |  |  | 876 median, 877 max per request (one worker) | OLD unresolved (30 s budget) per 200: 19.0 cold, 17.8 warm |
| UA 0325 17Z | FIELD | 106 (93.64–113) | 102 (92.93–110) | 231 [188–272] faster | 220 [178–254] faster |  |  | 678 (baseline 132) | 177/177 vs OLD; 1428/1428 vs recorded |
| UA 0325 17Z | FIELD-D | 18.13 (15.71–23.27) | 17.72 (15.94–20.03) | 1349 [913–1622] faster | 1268 [980–1482] faster |  |  | 191 (baseline 132) | 177/177 vs OLD; 1428/1428 vs recorded |
| UA 0325 17Z | MARGIN-1 | 113 (96.67–122) | 112 (95.74–121) | 216 [175–264] faster | 200 [163–247] faster | 0.93 [0.77–1.17] not distinguished (vs FIELD) | 0.91 [0.77–1.15] not distinguished (vs FIELD) | 702 (baseline 132) | 1509/1509 at m=60 vs widened FIELD |
| UA 0325 17Z | MARGIN-10 | 17.76 (14.27–18.11) | 16.37 (13.84–18.54) | 1378 [1173–1785] faster | 1373 [1059–1707] faster | 1.02 [0.87–1.63] not distinguished (vs FIELD-D) | 1.08 [0.86–1.45] not distinguished (vs FIELD-D) | 189 (baseline 132) | 177/177 vs OLD at 0; 1557/1557 vs FIELD at 0; 13581/13581 at m>0 vs widened FIELD |
| UA 0325 17Z | FIELD, sample specs only (OLD ÷ = on the same 200 requests, not scaled) | 17.41 (14.17–20.29) | 15.80 (13.08–19.76) | 181 [134–231] faster | 183 [128–232] faster |  |  | 292 (baseline 132) | timing row only |
| UA 0325 17Z | FIELD + route check, sample (OLD ÷ = on the same 200 requests, not scaled) | 57.70 (53.54–61.18) | 60.04 (50.87–61.54) | 54.47 [44.59–61.15] faster | 48.07 [40.98–59.65] faster |  |  | 292 (baseline 132) | 665 witness checks over all repeats, 0 failed |
| YD 0325 19Z | OLD (scaled) | 44651 (44041–46514); sampling 95% CI 43983–45821 | 40293 (37037–41391); sampling 95% CI 38699–40988 |  |  |  |  | 1278 median, 1337 max per request (one worker) | OLD unresolved (30 s budget) per 200: 45.2 cold, 30.8 warm |
| YD 0325 19Z | FIELD | 282 (221–306) | 289 (205–320) | 158 [144–210] faster | 139 [116–202] faster |  |  | 924 (baseline 254) | 142/142 vs OLD; 1561/1561 vs recorded |
| YD 0325 19Z | FIELD-D | 260 (193–279) | 262 (191–282) | 172 [158–241] faster | 154 [131–216] faster |  |  | 417 (baseline 254) | 142/142 vs OLD; 1561/1561 vs recorded |
| YD 0325 19Z | MARGIN-1 | 406 (399–416) | 417 (411–438) | 110 [106–117] faster | 96.57 [84.60–101] faster | 0.70 [0.53–0.77] slower (vs FIELD) | 0.69 [0.47–0.78] slower (vs FIELD) | 981 (baseline 254) | 1427/1427 at m=60 vs widened FIELD |
| YD 0325 19Z | MARGIN-10 | 272 (262–280) | 273 (251–284) | 164 [157–178] faster | 148 [131–165] faster | 0.95 [0.69–1.07] not distinguished (vs FIELD-D) | 0.96 [0.67–1.12] not distinguished (vs FIELD-D) | 410 (baseline 254) | 142/142 vs OLD at 0; 1810/1810 vs FIELD at 0; 12843/12843 at m>0 vs widened FIELD |
| YD 0325 19Z | FIELD, sample specs only (OLD ÷ = on the same 200 requests, not scaled) | 177 (129–206) | 185 (129–211) | 27.93 [23.63–39.77] faster | 24.13 [19.38–35.46] faster |  |  | 420 (baseline 254) | timing row only |
| YD 0325 19Z | FIELD + route check, sample (OLD ÷ = on the same 200 requests, not scaled) | 273 (212–305) | 284 (213–287) | 18.06 [15.95–24.28] faster | 15.69 [14.26–21.50] faster |  |  | 424 (baseline 254) | 855 witness checks over all repeats, 0 failed |
| YD 0325 23Z | OLD (scaled) | 31246 (30228–32366); sampling 95% CI 30519–32116 | 26337 (25209–27427); sampling 95% CI 25461–27236 |  |  |  |  | 653 median, 1348 max per request (one worker) | OLD unresolved (30 s budget) per 200: 8.0 cold, 5.6 warm |
| YD 0325 23Z | FIELD | 294 (281–318) | 297 (271–309) | 106 [94.94–115] faster | 88.78 [81.52–101] faster |  |  | 419 (baseline 250) | 189/189 vs OLD; 1624/1624 vs recorded |
| YD 0325 23Z | FIELD-D | 298 (282–307) | 294 (269–309) | 105 [98.59–115] faster | 89.44 [81.47–102] faster |  |  | 418 (baseline 250) | 189/189 vs OLD; 1624/1624 vs recorded |
| YD 0325 23Z | MARGIN-1 | 402 (370–418) | 424 (395–432) | 77.73 [72.35–87.43] faster | 62.06 [58.41–69.44] faster | 0.73 [0.67–0.86] slower (vs FIELD) | 0.70 [0.63–0.78] slower (vs FIELD) | 484 (baseline 250) | 1337/1337 at m=60 vs widened FIELD |
| YD 0325 23Z | MARGIN-10 | 286 (252–294) | 291 (253–304) | 109 [103–129] faster | 90.56 [83.02–109] faster | 1.04 [0.96–1.22] not distinguished (vs FIELD-D) | 1.01 [0.89–1.22] not distinguished (vs FIELD-D) | 407 (baseline 250) | 189/189 vs OLD at 0; 1673/1673 vs FIELD at 0; 12033/12033 at m>0 vs widened FIELD |
| YD 0325 23Z | FIELD, sample specs only (OLD ÷ = on the same 200 requests, not scaled) | 220 (202–224) | 222 (205–236) | 17.02 [16.14–19.20] faster | 14.20 [12.79–15.99] faster |  |  | 421 (baseline 250) | timing row only |
| YD 0325 23Z | FIELD + route check, sample (OLD ÷ = on the same 200 requests, not scaled) | 298 (277–326) | 302 (280–317) | 12.52 [11.10–13.96] faster | 10.44 [9.50–11.72] faster |  |  | 423 (baseline 250) | 895 witness checks over all repeats, 0 failed |
| YD 0326 08Z | OLD (scaled) | 28861 (26642–29808); sampling 95% CI 27764–29190 | 23106 (21793–26138); sampling 95% CI 22747–24256 |  |  |  |  | 652 median, 1499 max per request (one worker) | OLD unresolved (30 s budget) per 200: 7.2 cold, 5.8 warm |
| YD 0326 08Z | FIELD | 335 (304–346) | 340 (316–351) | 86.17 [77.11–98.18] faster | 68.03 [62.17–82.83] faster |  |  | 606 (baseline 249) | 191/191 vs OLD; 1591/1591 vs recorded |
| YD 0326 08Z | FIELD-D | 328 (285–350) | 328 (286–343) | 88.04 [76.09–104] faster | 70.48 [63.51–91.31] faster |  |  | 423 (baseline 249) | 191/191 vs OLD; 1591/1591 vs recorded |
| YD 0326 08Z | MARGIN-1 | 443 (435–464) | 455 (444–470) | 65.13 [57.39–68.46] faster | 50.78 [46.33–58.85] faster | 0.76 [0.65–0.79] slower (vs FIELD) | 0.75 [0.67–0.79] slower (vs FIELD) | 670 (baseline 249) | 1269/1269 at m=60 vs widened FIELD |
| YD 0326 08Z | MARGIN-10 | 306 (292–315) | 302 (298–329) | 94.26 [84.49–102] faster | 76.43 [66.21–87.81] faster | 1.07 [0.90–1.20] not distinguished (vs FIELD-D) | 1.08 [0.87–1.15] not distinguished (vs FIELD-D) | 412 (baseline 249) | 191/191 vs OLD at 0; 1641/1641 vs FIELD at 0; 11421/11421 at m>0 vs widened FIELD |
| YD 0326 08Z | FIELD, sample specs only (OLD ÷ = on the same 200 requests, not scaled) | 242 (221–251) | 240 (215–252) | 14.54 [12.96–16.43] faster | 11.75 [10.54–14.83] faster |  |  | 603 (baseline 249) | timing row only |
| YD 0326 08Z | FIELD + route check, sample (OLD ÷ = on the same 200 requests, not scaled) | 302 (297–328) | 316 (302–325) | 11.66 [9.89–12.21] faster | 8.90 [8.18–10.54] faster |  |  | 608 (baseline 249) | 920 witness checks over all repeats, 0 failed |

## 4 Where a new method is slower, or uses more

* **MARGIN-1 is slower than FIELD** (both give decisions and an arrival): ratio 0.69 to 0.95, "slower" in 7 of 12 cache-and-mode cells (all three Yeongdeok caches, cold and warm,
  and UA 03-23 warm), otherwise "not distinguished". It is never faster. The extra cost is building the field at the margin to extract the route.
* **MARGIN-10 is not faster than FIELD-D** (like for like, decisions only): "not distinguished" in 10 of 12 cells and "faster" only on UA 03-24 (1.2×). The result is that ten margins cost the same as one, not that they are cheaper.
* **Witness routes are the expensive part of FIELD on the Uiseong caches**: FIELD takes 174 s on UA 03-24 and FIELD-D 24 s, because 1,158 routes are extracted. The old method also returns routes.
* **Memory**: FIELD and MARGIN-1 exceed the old method's median worker on UA 03-24 (535 and 562 against 302 MB), and MARGIN-1 on YD 03-26 (670 against 652 MB). The old method's largest worker reached 1,499 MB.
* **One request**: the speed-up comes from answering every departure of every origin at once. A single request on its own was **not measured** for the field or the margin field, so nothing here says they are faster for one departure.

## 5 Accuracy

* **Old method against FIELD and MARGIN at margin 0**: 11,283 decided requests (5 repeats, cold and warm, 12,000 requests, 6 caches): **0 disagreements** with either, including the arrival second on every route. On the 1,097 sampled cases the old method decided in every repeat, also 0.
  Against the recorded verdicts of the finals run: 9,239 decided recorded cases, 0 disagreements with FIELD or with MARGIN at margin 0.
* **FIELD against MARGIN at margin 0**: all 9,722 cases (answer and arrival) and 1,574 origin issue sets, 0 differences.
* **MARGIN at other margins against the existing field on the widened instance**: 8,488 case answers at 60 s (with arrival) and 76,392 at the nine non-zero margins of the ten-margin read-off, plus 13,730 origin issue sets, 0 differences.
* **Route checks**: every FIELD witness checked by the unchanged full-policy checker on the sample: 0 failures (see the "FIELD + route check" rows).
* **What the old method did not decide**: 717 of 12,000 requests (6.0%). 507 reached its 30 s limit, and 210 are 21 cases whose origin is already in flame at that second (it refuses; the field says "no journey" on all 21). The old method's verdict varies between repeats on 57 cases, but only between "decided" and "unresolved" (time-limit effects), never between "route" and "no route".
  The unresolved requests are in the old method's timings at their measured time, so its times include the cases where it hit the limit.

## 6 Limits

* The old method was timed on 200 random requests per cache and scaled. The sampling interval is in the table. A full run was not made (about 9,700 requests at 7 to 20 s, five times, twice).
* One machine class, one pinned core on a shared virtual host. The probe shows modest noise; some repeat ranges are wide (for example FIELD on YD 03-25 19Z, 221 to 306 s cold).
* The old method's 30 s budget matches the finals; a larger budget would turn some unresolved requests into answers and raise its time.
* A separate study on a Mac (`research/kcf-bench-mac/`, merged in #228) compared the old method with the field on different job sets and a different machine and found 25 to 222×; the two are not combined. Its design differs (the old method run once on up to 500 jobs, no margin field, no cold and warm split).
* Not claimed: other machines, compiled versions of either method (none timed), instances unlike these, physical safety of any route, a speed-up for a single departure.

## 7 Deviations from the plan

* A1 (before timing): added FIELD-D, the sample-only row and the route-check row, and an untimed memory probe (the probe was not run; per-spec peak memory is not reported).
* A2 (during the run): OLD blocks interrupted by a restart are resumed, not re-run. One block straddled a restart; its requests keep their boot id.
* A3 (during the run): the session came back on a different machine class; data are kept per class and never pooled.
* The accuracy pass is run once, untimed, after all timing, on repeat 1's saved answers (the saved answers of the timed runs were recomputed and agree: 0 differences).
* Two git operations ran during timed blocks and a harness bug (task file names) was fixed after a dry run, before any timing.

## 8 Files

`BENCH_PLAN.md`; `results_hostB/{machine.json, ledger.jsonl, old.jsonl, field/, answers/, accuracy/, summary.json, tables.md, EVENTS.md}`; code `common.py, make_cases.py, run_field.py, run_old.py, driver.py, accuracy.py, analyze.py`; cases and the 200-request sample `cases/`.
Reproduce: `python3 research/kcf-bench/driver.py --work <dir> --results research/kcf-bench/results_x`, then `accuracy.py --results ...` and `analyze.py --results ...` (the benchmark takes about two days).
