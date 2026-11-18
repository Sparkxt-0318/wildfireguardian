# IDEA: lee-slope bypass. When embers fall more gently than the lee slope, the fire skips it (kcf-idea-forecast)

Stage 3 of five. Written before any reach was compared with the idea. Parameter values are frozen in `params.json`.

## 1. The idea in two sentences

A burning ember leaving a ridge crest descends at the angle whose tangent is (fall speed) / (wind speed). If that angle is shallower than the lee slope, the ember cannot land on the lee slope: it crosses the valley and lights the next windward slope, so the fire front never has to travel the lee slope or the lower windward slope, and its speed across ridged terrain rises by a factor that grows linearly with wind speed.

## 2. Variables

| symbol | meaning | unit | value used | source |
|---|---|---|---|---|
| U | wind speed at crest height, along the wind | m/s | ERA5 100 m wind | ASSUMED proxy |
| U10 | mean 10 m open wind | m/s | ERA5 10 m wind | as the 10% rule defines it |
| w_t | ember terminal fall speed | m/s | 5 (range 2.5–8) | Ellis 2010: bark flakes 2.5–8; karri 5.11 ± 1.08, jarrah 4.72 ± 1.84 |
| t_b | ember burning lifetime | s | 150 (range 120–180) | Tarifa, in Koo et al. 2010: 2–3 min |
| t_i | delay from landing to a spreading line | s | 300 (bracket 0–900) | ASSUMED. Lower end: cone ignition 19 s (Kwon & Lee 2023). Upper end: 300 m ÷ 20 m/min = 900 s, from the overrun rule of Alexander & Cruz 2006 as quoted in Page et al. 2019 |
| z0 | release height above ground | m | 20 | ASSUMED (canopy height); not a plume loft |
| θ_l, θ_w | lee and windward slope angles along the wind | rad | from the DEM | measured |
| H | ridge-to-valley relief | m | from the DEM | measured |
| λ | ridge spacing along the wind, H(cot θ_l + cot θ_w) | m | from the DEM | measured |
| r | head-fire rate over the ground, c·U10 | m/s | c = 0.1 | Cruz & Alexander 2019; their fitted slope is about 0.08 and the mean absolute error 1.11 km/h |
| v | effective rate of advance across ridges | m/s | predicted | |
| σ | share of along-wind ground distance the embers overfly | – | predicted | |

No constant in this table was fitted to a fire in this repo.

## 3. Governing relations

**Ember path.** Released at the crest (x = 0, height H + z0) into a horizontal wind U, falling at w_t:

  x(t) = U t, z(t) = H + z0 − w_t t, descent slope tan φ = w_t / U.

**Bypass number.**

  Π = U tan θ_l / w_t.

With z0 = 0 the ember strikes the lee slope if Π < 1 and clears it if Π > 1. The critical crest wind is

  U_c = w_t / tan θ_l.

**Landing point (Π > 1, symmetric ridges θ_l = θ_w = θ, z0 = 0).** The ember meets the next windward slope at the fraction of its height

  f = (Π − 1) / (Π + 1),

after a flight time t_f = (2H / w_t) / (Π + 1).

**Burnout condition.** The ember must still be burning when it lands: t_f ≤ t_b, i.e.

  Π ≥ 2 / Λ − 1, with Λ = w_t t_b / H.

So bypass needs Π ≥ max(1, 2/Λ − 1). High relief (small Λ) switches it off.

**Rate of advance.** Per ridge period the head fire only has to burn the upper (1 − f) of one windward slope; σ = 1 − (1 − f)/2 = Π/(Π + 1) of the ground is overflown. With head rate r over the ground:

  v = λ / ( t_i + t_f + (1 − σ) λ / r ), and the fire takes the faster of this and plain contiguous spread r.

In the limit t_i, t_f → 0:

  **v = r / (1 − σ) = r (1 + Π) = r (1 + U tan θ_l / w_t)  for Π > 1;  v = r for Π < 1.**

With r = c·U10 the advance is quadratic in wind above U_c, where the 10% rule is linear.

**Real terrain.** `terrain.py` does not assume triangles. It rotates the DEM so the wind blows along +x, ray-traces an ember from z0 above every cell, and solves the first-passage time along each row with head rate r and the jumps (each costing t_i + flight time; jumps longer than U·t_b are discarded). The speed-up factor is F = (L/r) / T, pooled over rows. On synthetic symmetric ridges (tan θ = 0.4, H = 300 m) it returns F = 2.10, 2.44, 3.10 at U = 15, 20, 30 m/s against 1 + Π = 2.20, 2.60, 3.40; the shortfall is the flight time and the 90 m grid.

**Reach prediction.** For issue hour t and horizon h:

  X1_h(t) = Σ_{τ = t+1..t+h} c·U10(τ)·Δt  (the 10% rule integrated: the baseline)
  X2_h(t) = Σ_{τ = t+1..t+h} c·U10(τ)·F(τ)·Δt  (this idea)

## 4. Dimensional check

Π = [m/s]·[–]/[m/s] is dimensionless. Λ = [m/s]·[s]/[m] is dimensionless. f and σ are ratios of lengths. t_f = [m]/[m/s] = s. v = [m] / ([s] + [m]/[m/s]) = m/s. X = [m/s]·[s] = m.

## 5. Limiting cases

- Flat ground, θ_l → 0: Π → 0, no bypass, v = r. The 10% rule is recovered.
- No wind, U → 0: Π → 0, v = r.
- Heavy embers, w_t → ∞: Π → 0, v = r. Light embers, w_t → 0: every lee slope is cleared, the known spotting-dominated behaviour.
- Very high relief, H → ∞: Λ → 0, the ember burns out in flight, v = r. Bypass is a property of short, steep ridges, not of big canyons.
- Long delay, t_i ≥ σλ/r: bypass is no faster than contiguous spread, v = r. This is the overrun rule of Alexander & Cruz (2006) seen from the other side.
- Cliff, θ_l → 90°: Π → ∞, f → 1, v → λ/(t_i + t_f): the fire moves at one ridge per ignition delay, bounded above by the wind speed itself.

## 6. Predictions that differ from the baseline by a measurable amount

1. **Threshold.** For w_t = 5 m/s, U_c = 5/tan θ_l: 10.7 m/s on a 25° lee slope, 13.7 m/s on 20°, 28 m/s on 10°. Below it the idea and the 10% rule agree. Above it they separate.
2. **Size.** On symmetric 22° ridges 1.5 km apart with U = 20 m/s and r = 1 m/s: 1 + Π = 2.6 with no delay, 1.6 with t_i = 300 s (numerical values from `terrain.py`: 2.44 and 1.64). A 5 h reach the baseline puts at 18 km becomes 29–44 km.
3. **Scaling.** Above threshold, reach divided by the wind run grows in proportion to F. The baseline says it does not depend on F. In a regression of the upper quantile of reach on X1·F^β the baseline is β = 0 and this idea is β = 1.
4. **Where spot fires land** (not testable with 2 km pixels): on the upper (1 − f) of windward slopes, and lee slopes burn after the next windward slope, not before.

## 7. What the idea does not claim

It says nothing about fuel, moisture or crown-fire transition; those sit inside r. It treats the flow above the valley as horizontal and uniform, which ignores lee eddies and crest speed-up. It uses one fall speed where real embers have a distribution.

## 8. Search record for this exact idea (18 November 2026)

Queries, run by a sub-agent and by me: firebrand "descent angle" OR "fall angle" "terminal velocity" "lee slope" spotting across valley ridge-to-ridge; ember "landing angle" OR "trajectory angle" "leeward slope" "steeper than" terminal velocity ratio; firebrand trajectory "terminal velocity" "wind speed" angle compared "slope angle"; spot fire "lee slope" skip OR "leapfrog" ridge "rate of spread" formula "ridge to ridge"; "effective rate of spread" formula spot fires "leapfrog" OR "hopping"; effective rate of spread across ridges and valleys undulating terrain harmonic mean; firebrand "opposite slope" OR "across the valley"; wildfire spotting across valley "ridge to ridge" embers effective rate of spread rugged terrain. One further query failed with a tool error and was not rerun.

**Result.** The mechanism is in print in words. The criterion Π = U tan θ_l / w_t > 1 and the rate v = r(1 + Π) were not found. So the claim of novelty is limited to the closed form.

**Three closest prior works.**

1. **Storey, Price, Almeida, Ribeiro, Bradstock & Sharples 2021**, "Experiments on the influence of spot fire and topography interaction on fire rate of spread", PLoS One 16(1):e0245132. Wind-tunnel hill (21° up, 31° down, 1.5 m/s) with spot fires placed by hand beyond the crest. Finding: spot fires let the fire overcome the slow downslope; it also reports McArthur's remark that slope becomes negligible when spotting crosses several ridges. *Difference:* spot positions are prescribed, not computed. There is no ember trajectory, no wind threshold, and no formula; spread is given as ratios for one geometry.
2. **FARSITE spotting module** (Finney; FARSITE technical documentation) and **Albini 1979**. FARSITE lets each ember fall at terminal velocity along the wind and checks the ground height at each step; Albini's maximum-distance model takes ridge-to-valley relief, horizontal distance and source position. *Difference:* both compute where one ember lands. Neither states the condition under which a lee slope is cleared, and neither turns landing positions into a rate of advance across repeated ridges. `terrain.py` uses the same ray-trace as FARSITE; that part is not new.
3. **Dold, Scott & Sanders 2011**, "The processes driving an ember storm", MODSIM 2011. A continuum model of spotting-dominated spread on flat ground with the result R ≈ w·t_e/(t_e + 0.3·t_s). *Difference:* no terrain. Its speed depends on ember lifetime and spotting time; the present idea's threshold and factor depend on the lee-slope angle, and on flat ground it reduces to r.

Also relevant: Hilton et al. 2019 (CFD of firebrands over a ridge; no criterion or rate); Sharples et al. 2012 (lee-slope lateral spread, with empirical thresholds of 20–25° and 20 km/h that concern the lee eddy, not the ember path); CSIRO Kataburn 2015 (assumes undulating terrain averages to the flat rate).

