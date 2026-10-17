# Official Route-Check API contract (copy)

This folder holds the planner's copy of the **official** WildfireGuardian Route-Check API contract. The
API session maintains it on branch `feat/api` as `contracts/wfg_api_v1.yaml` (OpenAPI 3.1), with its
change log in `contracts/CHANGELOG.md`. The planner builds against this copy (ARCHITECTURE.md §5). It
supersedes any earlier draft.

| File | Content |
|---|---|
| `wfg_api_v1.yaml` | the contract, byte-for-byte from the source commit, after one added first-line comment that names that commit |
| `CHANGELOG.md` | the API's change log, copied unchanged |
| `SOURCE_COMMIT` | the full id of the `feat/api` commit these files were copied from |

**Do not edit these three files by hand.** They are a copy. A fix to the contract belongs on `feat/api`;
refresh the copy afterwards.

## Refresh

```bash
planner/scripts/fetch_contract.sh            # fetch origin/feat/api, copy, print what changed
planner/scripts/fetch_contract.sh --check    # only report whether the copy is current (exit 4 = differs)
planner/scripts/fetch_contract.sh --offline  # use the remote-tracking ref already present (no network)
planner/scripts/fetch_contract.sh --branch other/branch   # another source branch, after review
```

The script runs `git fetch` into the remote-tracking ref `refs/remotes/origin/feat/api` only. It never
checks out, stashes, resets or otherwise changes the working branch.

It prints a diff summary against the previous copy, so contract changes are noticed:

- `info.version` before and after;
- endpoints and component schemas that were added, removed or changed;
- the first lines of a unified diff;
- the new lines in `CHANGELOG.md`.

If `feat/api` has no `contracts/wfg_api_v1.yaml`, the script scans the other remote heads (`git ls-remote
--heads origin` plus `git cat-file -e`) and reports what it finds:

| Exit code | Meaning |
|---|---|
| 0 | the copy was updated, or was already current |
| 1 | error |
| 2 | no remote head has the contract |
| 3 | the contract exists only on other heads, which are listed; rerun with `--branch` after checking which is the API's |
| 4 | `--check` found a difference |

## When `CHANGELOG.md` gains a version

A new version in the change log means the wire format may have changed. Update both consumers in the same
change:

1. **`planner/src/api/`**: wire types, client and adapter. The UI's internal model
   (`planner/src/domain/types.ts`, ARCHITECTURE.md §6) stays stable. Only the adapter maps new or changed
   fields onto it.
2. **`planner/mock_api/`**: update `server.py` so the mock serves the new contract:
   - `API_VERSION`;
   - the `REQUEST_SCHEMAS` mirror of the request components;
   - `REASON_CODES`;
   - new response fields and error codes.

   Then run `python3 -m pytest tests/planner/test_mock_api.py -q`. The tests validate every mock response
   against the copy, and `test_request_schemas_mirror_contract` fails until the mirror matches it.

Additive minor versions (v1.x) keep older clients working, but a client that enumerates values (such as
`ReasonCode`) must accept the new ones before the copy is refreshed.
