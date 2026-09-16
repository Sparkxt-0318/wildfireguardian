# Number re-run protocol

**Owner: A6. Version 1.0, 2026-09-16.**

Every number that could appear on a poster, in a paper, in the README or in
front of a judge is re-run by A6 before it enters `docs/NUMBERS.json`. A number
that A6 has not re-run is not a result, whatever it says in a report.

---

## 1. The problem this has to solve honestly

A6 and the modeling agents share one checkout, one environment and one set of
files. "Independent replication" in the usual sense is not available here, and
pretending otherwise would be the first fabricated claim in the program. So
independence is defined by what is actually achievable, and the gaps are stated
rather than papered over.

**What is achievable:**

- A6 starts from the **registered raw input**, identified by its sha256 in
  `research/data/REGISTRY.yaml`, not from the author's intermediate file.
- A6 runs the transformation through **a path A6 verified**, either by reading
  the author's script line by line before running it, or by writing a second
  path that does not import the author's model code.
- A6 checks the number against **the script and the artifact the author claims
  produced it**, by hashing that script and that artifact.
- A6 re-runs with the **pre-registered split**, recomputed from
  `research/eval/splits.py`, and compares split fingerprints.

**What is not achievable, and is recorded as a limitation in every report:**

- A6 cannot be blind to the author's result. By the time A6 re-runs, the number
  is known. This biases debugging towards stopping when the numbers agree.
  Mitigation: A6 writes the expected agreement tolerance before running, and a
  disagreement inside tolerance is still recorded with both values.
- A6 cannot verify a git commit, because A6 never runs git commands. The commit
  id is supplied by the orchestrator in the staging entry, and A6 verifies the
  weaker but checkable thing: the sha256 of the script file and of the input
  files at the moment of the re-run. **This is a real gap and it is listed as a
  human-gate item**, because linking a number to a commit needs somebody who is
  allowed to read the history.
- A6 cannot verify a number produced from a dataset that only exists on the
  author's machine. Such a number stays unverified and is not staged.

---

## 2. The four re-run levels

| level | what A6 did | accepted for |
|---|---|---|
| **L0** | read the author's output file or report | nothing, ever |
| **L1** | re-executed the author's script from the registered raw input, in a scratch directory outside the author's tree, after reading the script | secondary numbers |
| **L2** | re-derived the number by a path A6 wrote, from the registered raw input, without importing the author's model or feature code | headline numbers |
| **L3** | both L1 and L2, and they agree inside the declared tolerance | anything, and required for any number quoted to a judge |

L2 does not mean rewriting a Bayesian sampler. It means that the quantity that
gets quoted is computed by A6's own code from the author's posterior draws or
predictions, that the split is A6's, that the metric is A6's implementation, and
that the input is the registered raw file. Where the number is a model
coefficient rather than a metric, L2 means A6 refits from the same pre-registered
specification with an independently written model file and compares posteriors.

---

## 3. Tolerance

Declared **before** the re-run, in the staging entry.

- **Counts, row counts, sha256, dataset sizes, segment counts:** exact. Any
  difference is a finding.
- **Deterministic metrics on a fixed split:** exact to the printed precision.
  A difference here means the pipeline is not deterministic, which is itself the
  finding.
- **Stochastic quantities (posterior summaries, bootstrap intervals):** the
  pre-registration declares the seed and a tolerance. A6 additionally re-runs
  with at least two other seeds. If the quantity moves outside its tolerance
  across seeds, the number is reported as the range over seeds, never as the
  seeded point value, and the staging entry records the sweep.
- **Anything at or near a decision threshold:** if a number that is quoted as
  crossing a threshold falls inside tolerance of that threshold, the claim is
  scoped to "not distinguishable from the threshold" rather than reported as
  crossing it.

---

## 4. Staging, since `docs/NUMBERS.json` is a human gate

`docs/NUMBERS.json` sits outside `research/`, so no agent in this program writes
it. A number is staged twice instead: the direction proposes it in
`research/<direction>/numbers_staged.json` in the registrar's own `entry()`
shape, and A6 records the verification in `research/eval/numbers_staging.json`,
which A6 owns. Section 5 gives both shapes and the reason for the duplication.

States:

| state | meaning |
|---|---|
| `staged` | the author has proposed it; nothing has been re-run |
| `verified` | A6 re-ran it at the required level and it agrees inside tolerance |
| `disputed` | A6 re-ran it and it does not agree; both values are kept |
| `withdrawn` | leakage or an error was found after staging; the entry stays, marked |
| `withdrawn_pending_condition` | a blocking sign-off condition is open |
| `promoted` | John has registered it in `docs/NUMBERS.json`; the entry records the date |

The promotion path, in full:

1. A6 marks the entry `verified`.
2. The orchestrator raises a Waiting-on-John item in `research/TASKBOARD.md`
   carrying the entry block verbatim, the claim sentence with its uncertainty
   and its evaluation frame, the script and input hashes, and the split
   fingerprint.
3. John, or an agent working under John's explicit approval on that item, adds
   it to `docs/NUMBERS.json` through the repository's own registrar
   (`scripts/build_numbers.py`), which is the only supported way in.
4. The staging entry is updated to `promoted`, with the date. It is never
   deleted, because the staging file is the audit trail of what was proposed and
   what did not make it.

**Until an entry is `verified`, its number does not appear in prose anywhere in
`research/`,** not in a report, not in a figure caption, not in a table. A
worked example with synthetic inputs is allowed and says so on the same line,
which is also what keeps it clear of the forbidden-claims checker.

---

## 5. The registrar's shape, demanded now rather than after the fit

`docs/NUMBERS.json` is written only by `scripts/build_numbers.py`, and its
`entry()` helper fixes the shape of every registered number:

```
value, unit, source_file, json_path, derivation, config_hash,
config_hash_at_production, git_commit, sample, caveat,
forbidden_phrasings, check, reproducibility, reproducible
```

Two consequences bind this program, and both are cheap now and expensive later:

1. **`source_file` must be a committed JSON artifact and `json_path` a dotted
   path into it**, resolved by the registrar's `dig()` helper. A number that
   lives in a notebook, in a report, in a figure or in prose cannot be
   registered at all. So **every direction emits a committed JSON result
   artifact whose keys are addressable**, and the key path of every number that
   might be quoted is named **in the pre-registration**, before the fit. That is
   item P16 of `SIGNOFF.md`. Asking for it after a direction has fitted
   something means rewriting its output layer.
2. **Every entry carries its own `forbidden_phrasings` list and a `check`.**
   That is the repository's own mechanism for "this number may not be written
   bare", and it is the same mechanism as the graduation step in
   `research/FORBIDDEN_CLAIMS.md`: a result never becomes free to state bare, it
   becomes free to state with its interval and its evaluation frame. So the
   `forbidden_phrasings` of a research number are written by A6 at verification
   time, from the claim sentence, and they name the bare spellings that must
   never appear. The `check` is the assertion that ties the registered value
   back to the artifact.

A third consequence is a gap rather than a requirement: `entry()` reads
`REPRO[source_file]`, so a new research artifact also needs a reproducibility
record inside `scripts/build_numbers.py`. That is a change outside `research/`
and therefore a human gate, listed below as NH-A6-04.

### Where a number sits before it is registered

| stage | file | owner | shape |
|---|---|---|---|
| the direction proposes a number | `research/<direction>/numbers_staged.json` | the modeling agent | exactly the `entry()` shape above, with `git_commit` left empty for the orchestrator |
| A6 verifies it | `research/eval/numbers_staging.json` | A6 | the verification record, which embeds the proposed entry verbatim |
| John registers it | `docs/NUMBERS.json` | human gate | through `scripts/build_numbers.py` only |

Staging in the registrar's own shape means the eventual patch is mechanical
rather than a re-derivation, and it means a missing field is discovered at
pre-registration rather than the night before a poster.

### The A6 verification record

Every field is required. A missing field is a refusal to verify.

```json
{
  "id": "RES-ROADS-0001",
  "direction": "roads",
  "label": "held-out breach discrimination, primary metric",
  "registrar_entry": {
    "value": null,
    "unit": "ROC-AUC",
    "source_file": "research/roads/results/<name>.json",
    "json_path": "held_out.primary_metric.value",
    "derivation": "one sentence naming the script and the computation",
    "config_hash": null,
    "config_hash_at_production": null,
    "git_commit": "",
    "sample": "leave-one-complex-out over five fires, held-out complex named",
    "caveat": "",
    "forbidden_phrasings": [],
    "check": "",
    "reproducibility": null,
    "reproducible": false
  },
  "claim_sentence": "the exact sentence permitted, carrying interval and frame",
  "evaluation_frame": "the fires, complexes, years or blocks it was held out on",
  "uncertainty": {"type": "posterior interval", "level": 0.9, "low": null, "high": null},
  "prereg": {"path": "research/roads/PREREG_roads_YYYY-MM-DD.md", "version": 1},
  "signoff_record": "research/eval/signoffs/roads_YYYY-MM-DD_v1.md",
  "split": {"call": "leave_one_complex_out(fire_ids)", "kwargs": {}, "fingerprint": null},
  "inputs": [{"dataset_id": "kfs_forest_roads", "path": "", "sha256": ""}],
  "producer": {"script": "", "script_sha256": "", "commit_claimed": "",
               "seed": null, "python": "", "packages": {}},
  "rerun": {"level": "L0", "by": "A6", "date": null, "path": "",
            "value_obtained": null, "tolerance": null, "seed_sweep": [],
            "verdict": "not run"},
  "forbidden_claim_rules": ["RC-002", "RC-008"],
  "state": "staged",
  "notes": ""
}
```

`forbidden_claim_rules` lists the rules in `research/FORBIDDEN_CLAIMS.md` that
the claim sentence would break if it were written without its interval and its
frame, and it is what fills `registrar_entry.forbidden_phrasings`. It exists so
that the graduation step of that file has something to act on, rather than
somebody trying to remember which rule applied.

## 6. What A6 does on receiving a number

1. Refuse the entry outright if any field is missing, if the split fingerprint
   does not recompute, if `source_file` is not a committed JSON artifact whose
   `json_path` resolves, or if the dataset is not `verified` in the registry.
2. Hash the claimed script and the claimed inputs. Record the hashes.
3. Re-run at L1, then at L2 for anything headline.
4. Sweep the seeds if the quantity is stochastic.
5. Write the verdict, both values, and the tolerance into the entry.
6. Check the claim sentence against `research/FORBIDDEN_CLAIMS.md`, including
   that it carries its uncertainty and the fires or years it was held out on.
7. Run `research/shared/check_research_claims.py` over the tree and confirm it
   exits 0.
8. Only then mark `verified` and hand the entry to the orchestrator for the
   Waiting-on-John item.

---

## 7. Standing human-gate items this protocol creates

- **NH-A6-01.** A6 cannot verify the commit a number is attributed to, because
  agents in this program do not run git. Somebody with history access has to
  confirm that the script hash A6 recorded belongs to the commit claimed.
- **NH-A6-02.** Writing `docs/NUMBERS.json` is outside `research/` and stays
  John's, per decision D-001. Every promotion is one line of his time, so
  promotions are batched.
- **NH-A6-04.** A new research result artifact needs a reproducibility record
  in `scripts/build_numbers.py` before `entry()` can register anything from it.
  That file is outside `research/`, so the record is added by John or under his
  explicit approval, batched with the promotions of NH-A6-02.
- **NH-A6-03.** A6 is not blind to the author's result at re-run time. If the
  program ever wants a genuinely blind check, it needs a second checkout and a
  person who has not seen the report, which is outside what this round can do.
