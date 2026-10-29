# Verified request-window routing

This opt-in stack integrates the independently checked Caldor deadline repair, including the earlier signed-coordinate numerical and bounded-memory fixes. The 52 production Python files in `stack/` are byte-identical to the sealed repair candidate; `SOURCE_SHA256.json` records every hash. The historical release under `integration/kit` remains reproducible.

## What changes

- Generate a flame-contact-avoiding candidate and send every Z witness directly to the mandatory whole-journey checker, avoiding the optional eager thermal-rejection prefilter.
- Bind radiation work to the exact closed request window. Retain sources whose half-open activity intervals can intersect that window, taking the union across all members. Preserve full flame histories, original event cuts and geometric partition rules.
- Within the full checker, retain native source indices, full activity arrays and the original sparse/near selection policy. Calculate expensive geometry only for sources active during the request window. Uncomputed inactive geometry retains a conservative upper enclosure; it is not falsely assigned zero.
- Bind caches to the exact window and source identity. A changed window creates a fresh radiation object and kernel. Reject out-of-window queries and changed authority.

Hazard thresholds, destination occupancy, incurred dose, contact checking and publication requirements are retained. No unfinished check becomes a success. This is a cumulative implementation comparison, not attribution of all gains to one component.

## Verified results

See [the fresh original-panel replay](../../research/routing/request-window-20261029/README.md) for the 20 missions, both repetitions and both implementations, and the separately scoped six-mission Caldor/Rim result. Routing latency excludes offline independent verification and forecast generation. These remain model-relative research results.

## Use with the existing API

Use Python 3.12 and NumPy 1.26.4. From the repository root:

```sh
python -B experimental/window-routing/tests/test_full_checker_window.py -v
python -B experimental/window-routing/build_kit.py --out artifacts/window-kit
python integration/examples/run_frozen_case.py --kit artifacts/window-kit --out artifacts/window-uljin
```

Install the existing `integration` API package and fetch the evaluated inputs as described in the root README first. `build_kit.py` refuses an existing output or changed source hashes. It verifies the historical kit, overlays the sealed candidate, refreshes identity metadata and produces a separately identified kit. It does not change the historical release. Use `RDA_CAND`: the overlay's shared-checker `RDA_BASE` is not the unchanged historical reference used in the paired study.

The API's offline checker is separate from the timed routing request. The CLI refuses an existing replay output. CPU/macOS is the measured host; CI portability controls are distinct from a new performance campaign.

## Boundaries

The independent verifier checks actual frozen mathematical inputs and returned journeys; it does not validate those inputs against physical fire or prove evacuation safety. A finite regression suite does not prove every numerical enclosure for all possible inputs. Full global-proof and broader field-validation questions remain. Optional internal contact batching expects concrete sequences, not arbitrary single-use iterators.
