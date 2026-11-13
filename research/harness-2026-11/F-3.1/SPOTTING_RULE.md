# Spotting-distance envelope: per-place deadline shift (counting rule, committed before tabulating)

Results are **model statements on scenarios**: F-DYN SCENARIO, not what happened.

## Packets

* **Arrival raster.** Leo's shared `dilate(a, d_m, lag_s)` (F-DYN `fdyn/variants.py`, worktree at 4463892) is applied
  to the published kriged_mean TOA (`KFS_01_pswt_ok_toa.tif`):
  * d ∈ {0, 500, 1000, 2000} m;
  * **lag 0 s.** A spot ignites when its source cell does. This is the earliest-spot choice; it is not data.
  * The dilation is isotropic. There is no wind field in the KFS_01 inputs.
  * d = 0 is the identity. It is built from the same dilate code path, as a control that must reproduce kriged_mean.
* **Build.** Leo's `fdyn/build.py` with member set central, domain full_grid, the interim graphs and quantum 300 s.
  The arrival variant is named `dilate_<d>m_lag0s`.
* **Starts.** The 6 recorded starts (UA 03-23 01Z, 03-24 09Z, 03-25 17Z; YD 03-25 19Z, 03-25 23Z, 03-26 08Z), at
  5 h only. 8 h is not run.
* **Field.** `deadline_field/fdyn_run.py`, unchanged: cert field, fire-free control, and witnesses through the
  unchanged full checker on the packet as built.

## What is counted (per region-start and d; never pooled)

* **Per place:** the contiguous deadline at d (merged rule) and its shift against d = 0, in seconds.
* **Per region-start and d:**
  * number of places whose deadline moves earlier, and the median and maximum shift;
  * number of places whose deadline **moves before the start**: they had a contiguous deadline at d = 0 and have none
    at d;
  * number with no checked route at d = 0 already;
  * witness verdicts.
* **Control.** At d = 0 every place equals the kriged_mean v3.3 field. Any difference is reported as a fault.
* **Route side.** Priya supplies the matching route-side count (clearance below d). It is reported next to these
  counts, not merged with them.

## Not claimed

* Nothing about actual spotting distances in 2025.
* No downwind shape (no wind field).
* The lag-0 choice makes every shift an upper bound on the effect of isotropic spotting at distance d **under this
  dilation rule**, not a physical bound.
