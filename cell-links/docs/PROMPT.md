# Original prompt (verbatim)

Received 2026-10-14 (Asia/Shanghai). Reproduced exactly below.

---

Run this end to end. No plan mode needed; work through the steps and keep the records described at the bottom.

# Cell links: initial feasibility experiment

## The idea
Cell towers in mountain areas are often connected by point-to-point microwave links, and operators log received signal level (RSL) continuously. Since 2006, hydrologists have estimated rainfall from how much rain weakens these commercial microwave links (open tools such as pycomlink exist). Vegetation fire flames also attenuate microwaves, because potassium released from burning plants ionizes in the flame. Mphale and Heron (2007) reported 1.6 to 5.8 dB loss at 8 to 10.5 GHz through a controlled pine litter fire, with electron densities of roughly 0.5 to 1.4 x 10^16 m^-3 and collision frequencies of roughly 3.4 to 6.0 x 10^10 s^-1, and their bushfire work found the largest losses through the hottest zone. A compartment-fire study found flames affect the signal far more than smoke. If a wildfire crossing a link causes a detectable dip, existing links over Korean ridges could act as fire tripwires that work through smoke and at night.

## Question
Would a real wildfire crossing a real link produce a signal change detectable above normal link noise, and how often would links in Korean terrain actually be crossed by flames or the hot plume?

## Steps
1. Set up cell-links/ with the records listed below.
2. Parameters: build a cited table (docs/PARAMETERS.md) of flame and plume electron density, collision frequency, temperature profiles, flame heights for surface and crown fires, typical backhaul frequencies, link lengths, tower heights, and how operators log RSL (sampling interval, quantization). Verify the numbers above against the original papers and correct them if needed. Also check how common point-to-point microwave links are in Korean mountain areas today (Korea relies heavily on fiber) and list other existing radio links that could play the same role (broadcast relays, public-safety network links, forest monitoring relays).
3. Physics model:
   - Specific attenuation (dB per meter) of a weakly ionized flame from 1 to 80 GHz using a cold collisional plasma (Drude) model. Check that it reproduces the Mphale and Heron range for their geometry.
   - How ionization and temperature fall with height in the plume, and the attenuation for beams that pass through plume rather than flame.
   - Refractive effects of the hot turbulent plume (scintillation, beam bending): a jump in signal variance may be detectable even when mean attenuation is small.
4. Geometry on real terrain: use a free DEM (for example Copernicus 30 m) of the March 2025 Uiseong fire area, place plausible tower sites on ridge tops, create line-of-sight links of typical lengths, and compute first Fresnel zone clearance along each path. Report what fraction of link length a surface fire, a crown fire and the plume could actually intersect. If the DEM download fails, use synthetic terrain and say so.
5. Synthetic crossings: move a fire front across the terrain with a simple documented spread model, and generate each link's RSL time series as baseline plus realistic noise plus fire-induced attenuation and scintillation while flames or plume intersect the Fresnel zone.
6. Detection under realistic noise: if an open dataset of real link RSL is available (for example OpenMRG from Gothenburg; check availability and license), inject the synthetic fire signatures into real dry-weather series. Otherwise use a documented noise model. Evaluate a simple detector (baseline plus threshold on attenuation or rolling variance): detection probability versus false alarm rate, detection delay, and how well crossings of several links locate the front.
7. Confounders: rain (usually absent in fire weather, but check), automatic transmit power control that can hide fades unless transmit power is also logged, and coarse logging such as 15-minute minimum and maximum values in 1 dB steps.
8. Write cell-links/RESULTS.md: which frequencies, clearances and fire types this works for, a go/no-go recommendation, the single most informative next step (for example requesting link logs from a Korean operator for the 2025 fire period, or a small field test with two radios over a prescribed burn), and a principle demo for the booth (two ESP32 boards with a live signal-strength chart).

Time box: finish a complete first pass of every step before refining. Keep measured facts, modeled estimates and assumptions clearly separated, and never present a simulated result as observed.

## Working rules (three Claude Code sessions run in this repo at the same time)
- You are at the root of my WildfireGuardian repository. Confirm with `git rev-parse --show-toplevel` and a quick look at the README before starting.
- Work only inside cell-links/. Do not create, edit, move or delete anything outside it, including root files such as README, .gitignore or requirements. Reading the rest of the repo is fine.
- Do not modify or import the existing forecasting code. This work is isolated; copy ideas, not modules.
- Git: never switch branches, stash, rebase, reset or push. Stage only your folder (`git add cell-links/`), never `git add -A` or `git add .`. Commit at meaningful checkpoints with messages starting with [cell-links]. If you see a .git/index.lock error, another session is committing: wait a few seconds and retry.
- Python: use your own virtual environment at cell-links/.venv, list dependencies in cell-links/requirements.txt, and add cell-links/.gitignore for .venv, caches and large raw data. The machine is a MacBook Pro (M4 Pro, macOS); prefer packages that install cleanly on Apple Silicon.

## Record-keeping (required)
Keep these current inside cell-links/:
- README.md: what this is, why it exists, how to run everything, current status.
- LOG.md: append-only, dated entries in Asia/Shanghai time. Each entry: goal, exact commands, parameters, results with numbers, decisions, next step. Log every significant run, including failures.
- results/NUMBERS.json: every number quoted in README, RESULTS or LOG summaries, with the script, config and git commit that produced it.
- data/SOURCES.md: provenance for every external dataset, parameter and paper (source, URL, date accessed, license or permission).
- docs/PROMPT.md: this prompt, verbatim.
- Writing: plain, clear English, no em dashes, standard Markdown without decorative formatting.
- Figures: professional on the first try. Consistent style, readable font sizes, labeled axes with units, colorblind-safe palette, no clutter. Save PNG at 300 dpi plus SVG. Open and inspect every figure after saving, and fix anything cramped, clipped or overlapping before moving on.
