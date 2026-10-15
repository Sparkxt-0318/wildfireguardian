Run this end to end. No plan mode needed; work through the steps and keep the records described at the bottom.

# Last Gasp: initial feasibility experiment

## The idea
When a wildfire destroys a building, its connected devices go offline: smart electricity meters send a "last gasp" message to the utility just before losing power, Wi-Fi routers drop off the internet provider's network, and cheap radio tags stop broadcasting. If we know the minute each node died, we may be able to reconstruct the fire's spread minute by minute at building resolution, through smoke and at night. That would be far denser than satellite fire detections: polar-orbiting satellites (the FIRMS data WildfireGuardian uses) see a spot only a few times a day, and geostationary satellites are frequent but coarse. A node that dies well ahead of the front while nodes in between survive would be a recorded spot fire, with its jump distance.

The hard part: nodes also go offline for non-fire reasons. A failed power line blacks out every meter downstream at once, some last-gasp messages never arrive, and timestamps are noisy.

## Question
With realistic noise and confounders, how accurately can node death times reconstruct (a) the fire arrival-time map, (b) spot fire events, and (c) which outages were caused by fire versus the grid? At what node densities and message delivery rates does it work or break?

## Steps
1. Set up last-gasp/ with the records listed below.
2. Synthetic world:
   - Buildings as nodes. Prefer real OpenStreetMap building footprints for an area hit by the March 2025 Gyeongbuk fires (parts of Uiseong, Andong or Yeongdeok). Fall back to a synthetic layout if the download fails, and say so.
   - Ground-truth fire spread from a simple, documented model (eikonal or cellular automaton) with wind and a spotting kernel that creates spot fires ahead of the front. It only needs to be plausible: this experiment tests reconstruction, not fire physics. If FIRMS detections for a Korean fire already exist in the repo, you may read them (read only) to shape the spread.
   - A power distribution network: radial feeder trees along roads with fuses, so one upstream failure blacks out a whole branch.
3. Observation model: death time = fire arrival + random ignition delay + reporting delay; last-gasp delivery probability below 1; grid failures when fire reaches poles or lines upstream; random unrelated outages; clock jitter. Make every parameter configurable and document defaults with reasons or sources.
4. Reconstruction, simple to better:
   - Baseline: interpolate death times (for example inverse distance weighting).
   - Better: a method that respects fire physics, such as a monotone or eikonal-constrained fit, or a Gaussian process with outlier handling.
   - Spot fire detection: nodes dying early relative to the reconstructed front, with surviving nodes between them and the front.
   - Fire versus grid classification using network topology: a whole subtree dying within seconds looks like the grid; isolated, spatially progressive deaths look like fire.
5. Evaluation against ground truth: arrival-time error in minutes (median and 90th percentile), spot fire detection precision and recall with distance error, and outage classification accuracy. Sweep node density, delivery probability, timing noise and grid failure rate, and produce clear figures, including a side-by-side map of true versus reconstructed arrival times.
6. Real-world check (desk research only): the status of smart meter (AMI) deployment in Korea, whether last-gasp or outage events are logged, and who holds such data (utility, internet providers, mobile carriers). Cite sources.
7. Write last-gasp/RESULTS.md: what works, what breaks, required conditions, a go/no-go recommendation, the most useful real data to request next, and how this maps to a tabletop demo (about 25 ESP32 boards broadcasting heartbeats on a village map; when a node is "burned," the software rebuilds the front live).

Time box: finish a complete first pass of every step with simple versions before polishing any one method. All results are synthetic: label them that way everywhere and never present them as real-world performance.

## Working rules (three Claude Code sessions run in this repo at the same time)
- You are at the root of my WildfireGuardian repository. Confirm with `git rev-parse --show-toplevel` and a quick look at the README before starting.
- Work only inside last-gasp/. Do not create, edit, move or delete anything outside it, including root files such as README, .gitignore or requirements. Reading the rest of the repo is fine.
- Do not modify or import the existing forecasting code. This work is isolated; copy ideas, not modules.
- Git: never switch branches, stash, rebase, reset or push. Stage only your folder (`git add last-gasp/`), never `git add -A` or `git add .`. Commit at meaningful checkpoints with messages starting with [last-gasp]. If you see a .git/index.lock error, another session is committing: wait a few seconds and retry.
- Python: use your own virtual environment at last-gasp/.venv, list dependencies in last-gasp/requirements.txt, and add last-gasp/.gitignore for .venv, caches and large raw data. The machine is a MacBook Pro (M4 Pro, macOS); prefer packages that install cleanly on Apple Silicon.

## Record-keeping (required)
Keep these current inside last-gasp/:
- README.md: what this is, why it exists, how to run everything, current status.
- LOG.md: append-only, dated entries in Asia/Shanghai time. Each entry: goal, exact commands, parameters, results with numbers, decisions, next step. Log every significant run, including failures.
- results/NUMBERS.json: every number quoted in README, RESULTS or LOG summaries, with the script, config and git commit that produced it.
- data/SOURCES.md: provenance for every external dataset, parameter and paper (source, URL, date accessed, license or permission).
- docs/PROMPT.md: this prompt, verbatim.
- Writing: plain, clear English, no em dashes, standard Markdown without decorative formatting.
- Figures: professional on the first try. Consistent style, readable font sizes, labeled axes with units, colorblind-safe palette, no clutter. Save PNG at 300 dpi plus SVG. Open and inspect every figure after saving, and fix anything cramped, clipped or overlapping before moving on.
