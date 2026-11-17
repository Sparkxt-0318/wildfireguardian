# Radiant heat ahead of a moving front: why the frozen law caps at 0.703 kW/m², and a closed-form replacement

Status: **derived and checked here; accepted with stated limits** (section 5). Code: `kcf_heat/law.py`; tests: `tests/test_law.py`.
Units: kJ, kW, m, s.

## 1. The frozen cap

The frozen bridge (`integration/src/wfg_latest/bridge.py`, law `wfg.hazard.construction/1`) makes every ignited 375 m
cell emit for the scalar cell duration T. The emission is a uniform horizontal source sheet at 5 m with areal power
χ·c·H/T, seen by an upward receiver at 0 m, with transmissivity 1.

For a sheet of isotropic point emitters with areal power σ at height h above an upward receiver,

q = ∫ σ cos θ / (4π ρ²) dA = (σ/4π) ∫₀^∞ (h/ρ³) 2πr dr = σ/2,  with ρ² = r² + h².

The infinite sheet gives σ/2, and a finite cell gives less. So **q ≤ χ·c·H/(2T)** for every receiver and every time.

Packet values (`contract.py` POLICY):

* χ = 0.30;
* c = 10 kg/m² × 0.1 = 1 kg/m²;
* H = 18,608 kJ/kg;
* T = 11.52 s + 375 m / (341 m/h) = 3,970.46 s.

These give **q ≤ 0.3 × 18,608 / (2 × 3,970.46) = 0.7030 kW/m²**. F-3.1 recorded a maximum packet flux of
0.702 kW/m², which is consistent.

The cause: a point releases its c·H = 18,608 kJ/m² in t_r = 11.52 s, but the law spreads that energy over the
66 min the front needs to cross the cell. That is a factor T/t_r = 345 in emission density. In addition, a
horizontal sheet seen from below cannot represent a vertical flame zone seen from the side.

## 2. Line-source law (as proposed, re-derived)

**Assumptions**

* A1. A straight front advances at constant R (m/s) into uniform fuel with E_A = c·H (kJ/m²).
* A2. Each point flames for t_r, so the flaming zone has depth D = R·t_r. The heat release per metre of front is
  Byram's I = E_A·R (kW/m).
* A3. A fraction χ is radiated isotropically. The zone is collapsed to a line source of χ·I per metre at its
  centroid, D/2 behind the leading edge.
* A4. The receiver is on the centreline, at the line's height, and faces the line. There is no attenuation and no
  occlusion.
* A5. The front is long, or straight with half-width a.
* A6. Quasi-steady: R and I are constant while the receiver is within range.

**Flux.** A line element dℓ at lateral offset ℓ sends χI dℓ / (4π(s² + ℓ²)) through a unit area facing it, times
cos θ = s / √(s² + ℓ²). So

q = (χ I s / 4π) ∫₋ₐ^ₐ dℓ / (s² + ℓ²)^{3/2} = (χ I / (2π s)) · a / √(a² + s²),  where s = d + R·t_r/2.

For a → ∞ this is **q = χ I / (2π s)**. The finite-front factor is a/√(a² + s²). Both match the brief.

**Lead time.** Fix the receiver, and let the leading edge arrive τ seconds later. Then d = Rτ, s = R(τ + t_r/2) and
I = E_A R, so

q(τ) = χ E_A / (2π (τ + t_r/2)).

**R cancels.** q(τ) ≥ q* exactly when τ ≤ **T\* = χ E_A / (2π q\*) − t_r/2**. The halo distance is R·T\*.

* For a finite front, q(τ) = χE_A/(2π(τ + t_r/2)) · a/√(a² + R²(τ + t_r/2)²). This depends on R and is below the
  long-front value. The long-front T\* is therefore an **upper bound** on the lead time, which is the conservative
  direction for closing roads (`law.lead_time_finite`; tested).
* The time integral of q diverges logarithmically for an infinitely long front approaching from infinity. Any finite
  front or fuel bed bounds it. The thermal dose ∫q^{4/3}dt converges in either case.

## 3. Packet numbers

E_A = 18,608 kJ/m², χ = 0.30, t_r = 11.52 s and R = 341 m/h = 0.0947 m/s, so χE_A/(2π) = 888.5 kJ/m.

| q\* (kW/m²) | T\* exact | T\* (min) | rounded T\* used in routing | halo R·T\* | halo used (from rounded T\*, up to cm) |
|---:|---:|---:|---:|---:|---:|
| 10 | 83.09 s | 1.38 | 84 s | 7.87 m | 7.96 m |
| 5 | 171.9 s | 2.87 | 172 s | 16.29 m | 16.30 m |
| 2.5 | 349.6 s | 5.83 | 350 s | 33.12 m | 33.16 m |

The brief's 1.4, 2.9 and 5.8 min are confirmed.

At the leading edge (τ = 0) the long-front law gives χE_A/(π t_r) = 154 kW/m². Inside the flaming zone the line
model is not used; the contact rule applies there.

The halo is short compared with a 375 m cell. Most of the effect on routing therefore comes from **when** a road
cell closes (T\* earlier), not from how far the closure reaches sideways.

## 4. What the law depends on

* **T\* scales with χ·E_A** (consumed fuel × heat content × radiant fraction). These are the uncertain packet inputs.
  Doubling the consumed fuel doubles T\* + t_r/2.
* **T\* does not depend on R** for a long front. The 341 m/h packet spread rate enters only through the halo.
* **The leading-edge reference matters** (FDS_CHECK.md). The law puts the source D/2 behind the edge. In the C064
  model field, with the edge at HRRPUV > 20 kW/m³, the HRR centroid is 7.1 m behind the edge against D/2 = 5.7 m. The
  edge itself moves by several metres between thresholds of 5 and 100 kW/m³.

## 5. Verdict

The algebra is correct, and the law follows from A1–A6. It is **not rejected**. Against the C064 voxel field it is
about 10% high when distances are measured from the same leading edge, and within −8% to +5% when they are
measured from the HRR centroid (s ≥ 8 m). FDS's radiation solver gives far less (FDS_CHECK.md), so the law is
adopted as a conservative screening law, not as a validated flux.

Limits:

1. **A4 (no attenuation) is the weak assumption.** On C064, FDS's own radiation solver gives fluxes 6× (1–3 m) to
   ~100× (40–60 m) below the unattenuated voxel sum and below this law (FDS_CHECK.md). Against that reference the law
   closes roads early, which is the conservative direction. Whether a real fire is closer to FDS or to the
   unattenuated law is not established here (UNVERIFIED).
2. A3 places the line at receiver height. When s is comparable to the flame height, a vertically distributed source
   gives less flux than the line. This is also the safe direction.
3. A1 and A6 (a straight, steady front) do not hold at flanks, corners, junctions of fronts or in terrain. Multiple
   fronts add.
4. The constants are packet scenario values, not event calibrations: 10 kg/m² × 0.1 consumed is a grass-like
   1 kg/m², and χ = 0.30. A crown fire with 2–5 kg/m² consumed would scale T\* by 2–5 (not covered).
5. Not covered at all: convection, smoke, embers, terrain shading, vehicle shielding, crown-fire fuel load.
