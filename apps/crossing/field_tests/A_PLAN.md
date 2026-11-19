# Test A plan: flux plate against a Bunsen flame, and what that can say about the heat models

Written 2026-11-18, before any data. Session planned Friday 2026-11-20. **No measurement exists yet; every number in
this file is a calculation from stated assumptions, not a result.** Code: `bunsen_models.py` (curves),
`a_bunsen_analyse.py` (CSV -> table, figure, verdict), `a_bunsen_synth.py` + `tests/test_a_bunsen.py` (synthetic
checks only). This plan supersedes the run timing and plate size in `protocols/A_flux_plate.md`; that sheet's
safety, set-up and hardware sections still apply.

**The short answer to section 4, because it changes how to read the rest:** a Bunsen flame cannot tell the
closed-form law from the FDS voxel sum (their shapes differ by 0.1 % over 0.10-0.40 m), cannot test the FDS radiometer
curve at all (it cannot be scaled), and the radiant fraction chi, which is unknown to a factor of several, multiplies
every curve. What the session *can* do is check the plate-and-analysis chain, measure chi_eff of this flame, and test
that the near-field falloff follows an unattenuated source geometry. It cannot decide the 6-100x dispute.

## 0. Open items before Friday (each affects the result)

1. **Risk assessment** signed, scan on the laptop (`--risk-assessment`, `--supervisor`) if `a_flux_record.py` is used.
2. **Logging format.** `a_bunsen_analyse.py` reads one tidy CSV (section 1.5). `a_flux_record.py` writes
   `jsonl.gz` run directories, not this CSV, and its default phases are 60/180/300 s, not this plan's. A converter was
   not written (no real recorder output to check it against). Either log CSV directly, or ask for the converter.
3. **Flame size and flow** must be measured and entered in `sheets/A_plan_inputs.yaml` (`gas_flow_l_min`, flame
   `L`, `D`). The analysis refuses to run while they are null.
4. A **second, shielded thermocouple (`gas_c`)** next to the plate is optional but is the only way to bound
   convection (section 5). Not in the unit's current channel list as far as I checked; use a spare K bead if you have one.
5. This repo state: `apps/crossing` lives on `hardware/vehicle-unit`; this work is on branch
   `claude/bunsen-flame-heat-plan-gzf70y` (merged from it), not pushed to `hardware/vehicle-unit` itself.

## 1. Design, and how flux is computed

### 1.1 Distances, repeats, run length

| item | value | why |
|---|---|---|
| distance r | 0.10, 0.15, 0.20, 0.30, 0.40 m, burner axis to plate face | matches the printed jig marks; flux changes 14x across them; 0.10 m is the first place the finite flame length shows (`closed form / point` = 0.86) |
| repeats | 3 per distance, order randomised within a distance | detects drift and repeatability; 15 runs |
| run length | **60 s exposure** | what you specified |
| around each run | 30 s shielded baseline before (shield on, burner lit), 60 s shielded tail after | recorded in the same file; not counted as run length. The baseline sets the constant bias, the tail is a cool-down check |
| order between distances | far to near (0.40 first) | stepping closer only after the previous peak is known |
| between runs | plate within 1 K of room air | with C = 3.45 kJ/m2K and about 14-19 W/m2K, tau is about 3 min, so waiting is 5-8 min after a 5-13 K rise; plan about 3 h for 15 runs plus two cool-downs |
| cool-down curves | 2 dedicated runs, plate heated to about 50 C then burner removed and gas off, 300 s | covers the plate temperature range of the exposure runs (peak below about 45 C by the numbers below) |

Expected plate rise over 60 s (illustration: methane 1.0 L/min, Q = 0.565 kW, L = 0.12 m, D = 0.02 m, alpha = 0.95;
calculation, not measured; ignores loss, so slightly high):

| r (m) | flux at chi = 0.03 / 0.10 / 0.20 (kW/m2) | rise in 60 s (K) |
|---|---|---|
| 0.10 | 0.115 / 0.382 / 0.763 | 1.9 / 6.3 / 12.6 |
| 0.15 | 0.055 / 0.185 / 0.369 | 0.9 / 3.1 / 6.1 |
| 0.20 | 0.032 / 0.107 / 0.215 | 0.5 / 1.8 / 3.5 |
| 0.30 | 0.015 / 0.049 / 0.098 | 0.2 / 0.8 / 1.6 |
| 0.40 | 0.008 / 0.028 / 0.056 | 0.1 / 0.5 / 0.9 |

Two consequences. (i) **By radiation alone the plate cannot approach 70 C** (about 21 + 13 = 34 C worst case; 1.0 L/min
at chi 0.2 and 0.10 m gives +22 K). The 70 C limit protects against what this table leaves out: flame contact, plume
impingement, a leaning flame, a mistake in distance. Keep the live abort: gas off and shield on at 60 C, and the
recorder's hard stop at 70 C. The analysis marks any run with a sample >= 70 C as UNUSABLE and excludes it, never drops it. (ii) At
0.30-0.40 m and low chi the 60 s rise is below 0.5 K, about two MAX31855 steps (0.25 C). The far points may fall
below the detection floor (`q/u < 3`); the analysis then excludes them from the shape test and lists them. If chi
turns out low, raise the flow rather than shortening the distances (section 4).

### 1.2 From temperature trace to flux

Thin-skin (lumped) calorimeter, per unit front-face area, with C = rho cp d = 8960 x 385 x 0.001 = 3450 J/m2K (30 mm
disc, area 7.07e-4 m2; area does not enter the energy balance, only the finite-plate averaging in section 2):

    C dT/dt = alpha q_inc - loss(T),     loss(T) = h (T - Ta) + eps sigma (T^4 - Ta^4)

Assumptions: the disc is isothermal (Biot number h d / k is about 4e-5 for copper); the thermocouple reads the disc;
alpha for the flame spectrum is 0.95 (assumed, grey, same eps for the room); constant rho, cp; q_inc includes any
convective gas heating (not separable, section 5); h, eps lump front, back, edge (13 % of the face area) and mount losses.

**Mean flux over the exposure window, by integrating the balance** (`a_bunsen_analyse.flux_of_run`), not by
differentiating the noisy trace:

    q_mean = [ C (T(t2) - T(t1)) + integral_{t1}^{t2} loss(T(t), Ta(t)) dt ] / (alpha (t2 - t1))  -  q_baseline

t1 = shield off, t2 = t1 + 60 s. T(t1) and T(t2) are least-squares line values over the 6 s before each (quantisation
0.25 C averages down). q_baseline is the apparent flux of the 30 s shielded baseline (slope and loss at that
time), subtracted as a constant: it removes drift, a constant plate-minus-air thermocouple offset, and room
radiation that is common to baseline and exposure. A derivative-based flux trace (`crossing.flux.FluxEstimator`) is
fine for plotting but is not the result: its noise is about 0.35 kW/m2 per 1 s window (flux.py), 10-100x the
signal at 0.30-0.40 m.

### 1.3 The heat-loss term from the cool-down curve

`crossing.flux.fit_cooldown` on each dedicated cool-down run: with no flux, C dT/dt = -loss(T), so a linear
least-squares fit of -C dT/dt (5 s local-quadratic derivative, points with T - Ta >= 5 K) against h (T - Ta) +
eps sigma (T^4 - Ta^4) gives h with eps fixed at 0.95. The model uses the mean h of the cool-downs. Its relative
uncertainty is the larger of the run-to-run spread and 15 % (one still-air fit does not cover a draught), 25 % if only
one cool-down is usable, 50 % and flagged UNFITTED if none. The loss integral enters q directly; at the near distances it
is **about 15-40 % of the absorbed energy** (synthetic-model estimate with h = 14, not measured), so it matters
mostly where the signal is largest.

Validity limits: the fit covers about 27-50 C (not below T - Ta = 5 K); a single lumped h is a linearisation of natural
convection (h grows with T - Ta); h is for still air with the disc in the same position and mount as in the exposure
runs. Same orientation, no fan, doors closed. Heated side up/sideways is irrelevant only if the disc is not moved.

### 1.4 Quality rules (applied by the script, reported not hidden)

Run unusable if: any sample >= 70 C; baseline shorter than 30 s (or <40 samples); exposure window incomplete or with a
gap > 1 s; thermocouple fault samples are dropped and counted. A distance enters the shape test only with
`q / u >= 3`.

### 1.5 CSV format

One file, one row per sample (about 10 Hz): `run_id, t_s, plate_c, air_c` required; per exposure run `kind`
(`exposure`/`cooldown`), `distance_m`, `repeat`; optional `phase` (`baseline`/`exposure`/`tail`; otherwise **t_s = 0 is
shield off**, baseline is t_s < 0), `fault` (non-empty = drop the sample), `gas_c`. Command:

```bash
cd apps/crossing
python -m field_tests.a_bunsen_analyse LOG.csv --sheet field_tests/sheets/A_plan_inputs.yaml --out records/field_tests/A/analysis
```

Outputs: `A_bunsen_runs.csv`, `A_bunsen_table.csv`, `A_bunsen_compare.csv`, `A_bunsen_figure.png`,
`A_bunsen_snippet.md` (paste into RESULTS.md), `A_bunsen_summary.json`. Add `--simulated` only for synthetic input
(it watermarks every output); real data must not carry it.

## 2. Scaling each curve from a forest front to a Bunsen flame

Common to all: the forest laws describe a steady front moving at R into fuel E_A with residence time t_r. A Bunsen
flame is stationary, so **E_A, t_r, R and the lead-time form T* drop out; none of the lead-time claims
(T* = chi E_A/(2 pi q*) - t_r/2) can be tested here.** What remains testable is the **radiant geometry**: how flux falls
with distance from a source of given power. Every curve is linear in chi and in Q, with Q = flow x LHV x efficiency
measured on the day.

### 2.1 Closed-form line-source law (scalable, with assumptions)

Kept as q = chi I / (2 pi s) x a / sqrt(a^2 + s^2) (kcf-heat `law.line_flux_s`, called by file path, not copied).
Mapping: the flame is a **vertical line** of length L = visible flame height, half-length a = L/2, I = Q/L (kW per
metre of flame length), s = r, receiver at flame mid-height on the perpendicular bisector facing the axis. This is the
same integral as the forest law with the line rotated from horizontal to vertical. The 30 mm plate is averaged
numerically over its area (1-3 %). Assumptions, in the order of the law's A1-A6:
A1/A6 steady: true for a laminar Bunsen, with flicker. A2 depth D = R t_r: replaced by the flame's own geometry (not applicable).
A3 isotropic emission, uniform along L: false in detail (the blue inner cone and the tip emit differently; shifting the
emission centroid 2 cm changes q by 3 % at 0.10 m, L +-2 cm by +-4 %: `bunsen_models` sensitivity runs). A4 no absorption,
receiver at line height, no occlusion: path absorption over 0.4 m is about 1 % (section 4), the plate is at mid-height by set-up.
A5 finite front: here essential, a = 0.06 m is comparable to r. A **line of finite length is not what the law was derived for in
the forest** (a = 30 m >> s): the Bunsen test exercises the finite-length factor and the 1/s -> 1/s^2 transition, not the
long-front 1/s regime that the routing uses. The older mapping in `a_flux_analyse.py` (a = D/2, I = Q/D) is kept as
`closed_form_repo`; it is a horizontal 2 cm line and collapses onto the point source (within 1.2 % at 0.10 m), so it
is a different statement from the vertical line above and is shown only as a variant. Result: the closed form is
**0.86 x point source at 0.10 m, 0.99 x at 0.40 m**.

### 2.2 FDS voxel sum (scalable: it is geometry)

The voxel sum is chi x HRRPUV x dV, inverse square, receiver cosine, no absorption, summed over voxels. That applies
to any heat-release field, so it is applied unchanged to a **uniform emitting cylinder** (D x L, 4 x 12 x 24 midpoint
nodes) with total power Q, the plate averaged over its area. This is a defensible scaling because nothing in it
depends on size. Assumption: uniform emission through the flame volume. Result: within 0.1 % in shape of the
closed form (0.86 x point at 0.10 m, 0.99 at 0.40 m). They agree because they are the same optically thin integral.

### 2.3 FDS radiometer curve (**cannot be scaled defensibly**)

The C064 radiometer curve is 6x (1-3 m) to about 100x (40-60 m) below the voxel sum. The kcf-heat fit says FDS behaves
as if flame cells absorb with kappa_f = 0.3 /m and the path with kappa_a = 0.03 /m (`b2_absorption_fit.jsonl`,
rms-log 0.52; interpretation only, UNVERIFIED, grid-dependent at 1 m cells). Scaling the curve to a Bunsen flame would
need a similarity argument, and none holds:

* The deficit comes from optical depth: kappa_f x flame depth (11 m) plus kappa_a x path (1-60 m), tau of about 1-3. At Bunsen
  scale it is 0.3 x 0.02 + 0.03 x 0.4 = **0.018** (a 2 % effect). The mechanism does not scale down.
* The curve is a function of d/D, d/a and tau, but a 12 cm vertical flame is not geometrically similar to an 11 m deep,
  60 m wide front, and its heat release density (about 1.5e4 kW/m3) is 2-3 orders above C064's cell values (tens to a few hundred kW/m3).
* Multiplying the curve by I/4473 (as `crossing.heat.fds_reference` does) fixes the unit, not the physics: it keeps the
  shape in metres, which would put 0.1-0.4 m at the FDS curve's near edge (inside its 1 m cells).

So the curve is **not scaled**. The only statement possible is `fds_fit_transfer`: the voxel sum with the fitted
Beer-Lambert factor applied unchanged to the Bunsen cylinder. It is 0.99 x the voxel sum, which is the result that
matters: if the fit's absorption were real and scalable, it would be invisible here. It is plotted, tabulated and never
eligible to be "favoured". The honest version of the FDS test is a different experiment (section 4).

## 3. Metric, and what would favour each curve

Because chi is unknown (assumed 0.03-0.20, not measured) and multiplies every curve, a level comparison only returns chi.
So:

* **Level (reported, not a test):** chi_eff = measured / curve(chi = 1), weighted over usable distances, with
  uncertainty including alpha (3 %) and Q (10 %). A curve is *credible* only if chi_eff is inside 0.01-0.30 (prior).
* **Shape (the test):** with chi_eff free, chi^2 = sum over usable distances of ((ln q_i - ln q_curve,i - ln chi_eff) / sigma_i)^2,
  dof = n - 1, sigma_i the random uncertainty of the mean (trace noise, baseline, loss, timing, 0.003 kW/m2 floor,
  repeat scatter, and 2 mm distance error times the curve's local exponent). p from chi^2 (Wilson-Hilferty).
* **Exponent:** measured n in q ~ r^-n beside each curve's n over the same distances (closed form 1.72-1.98, voxel
  1.72-1.98, point 2.00).

**Pre-registered rules (in the code, `a_bunsen_analyse.verdict`; do not change after data):** a distance counts if
q/u >= 3; at least 3 distances. A curve is *acceptable* if p >= 0.05 and chi_eff in the prior. A curve is *favoured* if
acceptable and every other scalable curve (closed form, voxel sum, point) is worse by delta chi^2 >= 9. Otherwise "no curve
favoured". `fds_fit_transfer` is reported, never favoured.

What would favour each, honestly:

| outcome | reading |
|---|---|
| closed form acceptable, point rejected (delta chi^2 >= 9), voxel sum not separable | consistent with a **finite-length unattenuated line/volume source**. It favours the closed form **over the point source only**. It does not favour it over the voxel sum: designed-in, their shapes differ by 0.1 % |
| point source acceptable and closed form not | the flame is more compact than a 12 cm line, or the flame-height input is wrong (check L); not evidence about the forest law |
| all scalable curves acceptable, delta chi^2 < 9 | what the numbers below predict. No model is favoured |
| all rejected, chi_eff plausible | a measurement problem first: convection (section 5), flame leaning, drift, distance error, flame size; not a model failure |
| chi_eff outside 0.01-0.30 | the curve is not credible for this flame, or Q/L/D are wrong, or convection dominates |
| **nothing here can favour the FDS radiometer curve** | it predicts the voxel sum within 2 % at this scale; an observed deficit would be absorbed into chi_eff |

## 4. Can a Bunsen flame discriminate? No, for the question that matters

Calculation (`bunsen_models.shape_separation`, Q = 0.565 kW, L = 0.12, D = 0.02, r = 0.10-0.40, chi free):

| pair | max shape difference | separation (in sigma) at per-distance error 3 % / 5 % / 10 % |
|---|---|---|
| closed form vs voxel sum | **0.12 %** | 0.05 / 0.03 / 0.02 |
| voxel sum vs FDS-fit transfer | 0.5 % | 0.24 / 0.14 / 0.07 |
| closed form vs point source | 9.4 % | **3.7 / 2.2 / 1.1** |

Only the last pair reaches the 3-sigma bar, and only if every distance is good to 3 %, which section 5 says is
unlikely at 0.10 m. The two curves under dispute coincide at this
scale because the flame is optically thin (tau = 0.018) and the closed form is the same integral as the voxel sum. The
6-100x gap is an optical-depth effect, and FDS's version of it is tied to 1 m cells and a fitted kappa.

What a Bunsen test **can** show: whether the plate and the energy-balance chain measure a plausible flux; chi_eff of
this flame; whether q falls like an unattenuated finite source (the point-source-vs-line result above, marginal).

### What would discriminate

The closed form and FDS differ by tau, so the test fire needs tau comparable to the fitted FDS absorption (kappa_f D +
kappa_a d). Using the fit as written: flame depth D >= about 2-3 m gives tau of 0.6-0.9 (factor 0.4-0.55 in flux) at
zero distance, or a path of about 25 m (0.75); anything that gives a factor >= 2 in flux, 3x the 15-20 % that a good radiometer
measurement carries. Versus the Bunsen's 0.018, that is **about 40x more optical depth**. Concretely, a fire with:

* a flame zone **>= 2-3 m deep** and **>= about 10 m wide** (so the closed form's finite-front factor is not
  dominant and a >> s at the nearer distances), and a heat release of **at least about 2 MW**. By hand with the closed form
  (chi 0.3, I = 200 kW/m over a 10 m front, a = 5 m): about 0.4 kW/m2 at 10 m and 0.12 kW/m2 at 20 m. An FDS-like
  attenuation of 10-30x would put the 20 m value at 0.004-0.012 kW/m2, below a radiometer floor of about 0.02-0.05 kW/m2, so
  the two predictions would be told apart by presence or absence of a signal;
* radiometers (water-cooled Schmidt-Boelter or Gardon, not a bare plate) at 3, 5, 8, 12, 20, 30 m, measured flame geometry and HRR (mass loss or gas flow);
* run by the fire service on a prepared site: a gas line burner, wood crib or pool of this size, or a prescribed grass burn. Not a bench test.

Cheaper first steps that need no fire, and are not done here: (a) rerun FDS C064 at 0.5 m and 0.25 m cells: if the radiometer
gap closes with resolution, the 6-100x is a grid artefact; (b) check published radiometer data from instrumented
grass/prescribed fires against both laws (not verified or searched here).

## 5. Measurement uncertainty

Per-term sizes are assumptions or datasheet values from memory (UNVERIFIED) unless marked "from the data". The analysis
reports the random terms per run (`A_bunsen_runs.csv`, columns `u_*`) and adds common-mode terms to chi_eff.

| source | size | treatment |
|---|---|---|
| Thermocouple absolute error (K type + MAX31855, datasheet about +-2 C) | irrelevant to a **difference** in T; matters through T - Ta | plate and air TC offset (a few tenths of K, up to 2 K) is constant, removed to first order by the baseline subtraction. Check: 30 min unpowered, read both, note the offset |
| Thermocouple gain, contact lag, lead conduction | gain about 0.5 % (assumed); lag ms-seconds, negligible against 60 s; wire conduction is a small extra loss lumped into h | not separately modelled |
| Quantisation (0.25 C) and read noise | 1 sigma on T(t2) - T(t1) of a few hundredths K (from the data: `u_trace_noise`) | in per-run u; at far points this and the baseline dominate |
| Baseline / room drift | 0.0004 K/s assumed in the synthetic test; real unknown | baseline subtraction; residual in a 0.003 kW/m2 floor (assumed); set 30 s baseline, doors closed |
| **Absorptivity alpha of the paint** | 0.95 +- 0.03 assumed; real soot-contaminated or heat-aged paint can be lower; differs between 1500 K flame spectrum and 300 K loss | 3 % common to all distances; goes into chi_eff only |
| **Emissivity eps in the loss** | 0.95 fixed; h and eps are not separable over a 25 K range | h absorbs it; the plate is cooler than 50 C so the error is in the radiative part of the loss (about 5 W/m2K x error) |
| **Convection** | **unknown; probably the largest term at 0.10 m**. A gas layer 2 K above the room at the plate with h of 10 W/m2K gives 0.02 kW/m2, 5 % of the 0.10 m signal at chi 0.1 and half the 0.30-0.40 m signal at chi 0.03 | added in quadrature to every run's u as 0.02 kW/m2 (`--conv-kw-m2`, ASSUMED); with a `gas_c` thermocouple it is h x (mean gas - air) instead (`_conv_term`). Not subtracted. Keep the plate beside the flame, flame vertical, no draught. Report as a limit, not corrected |
| Plate heating | rise 0.1-22 K in 60 s (table 1.1) | loss model covers it; loss is 15-40 % of the absorbed energy near the flame; u_h 15-25 % of that is 3-10 % of q |
| Distance | jig +-2 mm, flame axis definition +-3 mm, wobble | 2 mm per run, times the local exponent: 4 % at 0.10 m, 1 % at 0.40 m in q; flame wobble not modelled |
| Flame geometry (L, D, emission centroid) | L +-2 cm, shift 2 cm | +-4 % at 0.10 m (L), 3 % (shift), under 1 % at 0.30-0.40 m. Flame height is the one input to measure well |
| Burner power Q | rotameter +-5-10 %, LHV (natural gas +-5 %), efficiency 1.0 assumed | 10 % common; chi_eff only |
| Shield re-radiation / timing | the shield warms; shield removal takes about 1 s | 1 s of 60 = 1.7 % per run (in u). Use a foil-faced shield, keep baseline ahead of the flame |
| Shield-off baseline vs radiative background | baseline is at far-distance flux, not zero | baseline subtraction only removes bias, not real baseline flux |

Combined (my estimate, not computed on data): **about 6-10 % per distance near the flame, dominated by loss model, distance, flame
geometry; 3 % alpha and 10 % Q common to all; 20-100 % at 0.30-0.40 m when chi is low** (floor 0.003-0.005 kW/m2 against 0.01-0.03).
Systematic common-mode terms (alpha, Q, convection) shift chi_eff, not the shape, except convection which is
distance dependent and **can mimic a shallower exponent**.

## 6. What this session will and will not tell you

Will: whether the thin-skin chain returns a flux of the expected size from a flame of known power; chi_eff and its
uncertainty; the near-field exponent of this flame; a record of failures (runs that exceeded limits, below the floor).
Will not: choose between the closed-form law and the FDS voxel sum; test the FDS radiometer curve; test lead time,
spread rate or any fuel-bed behaviour; say anything about a wildland fire. If the verdict reads "NO CURVE FAVOURED", that is the
expected outcome, and it is a statement about the Bunsen flame's power to discriminate, not evidence for or against any model.
