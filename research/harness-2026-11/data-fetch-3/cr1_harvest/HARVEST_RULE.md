# CR1 in-season IR harvest: rule file

Written 13 Nov 2026, before any script. This file is never edited; later changes go in a new file.

The script implements these rules. It has been run ONLY on a synthetic fixture. Real use waits for the 2027 season and the orchestrator's go, and Hannah reviews it first.

## Scope

1. **Season.** 2027 only.
   - `--year` must equal 2027. Any other value exits with an error before any request.
   - 2025 and 2026 are named in the refusal message.
2. **Source tree.** `<root>/<region>/<year>/<INCIDENT>/IR/<YYYYMMDD>/`, under the public incident_specific_maps root, as reported by the owner.
   - The root is passed on the command line. No default is hard-coded.
3. **Path guards.** Each guard applies to every URL or path before it is requested, and a violation is refused, not skipped silently.
   - The year segment must be exactly the requested year.
   - Any path containing a `protected` segment is refused.
   - No path may climb above the root (`..`, absolute redirects, or a different host).
4. **Files taken.** Only IR products in an `IR/<YYYYMMDD>/` folder, with suffix `.shp .shx .dbf .prj .cpg .kmz .kml .zip .pdf`. Everything else is listed in the log as "not taken".

## Behaviour

5. **Read-only listing.**
   - It reads Apache-style directory index pages: `href` targets only, no scripts.
   - At most one request per `--spacing` seconds (default 2.0).
   - The client identity is fixed (`wfg-cr1-harvest/1`) and is never changed.
6. **Idempotent.**
   - `state.json` maps each relative path to `{sha256, size, first_seen_utc}`.
   - A file already in state with a matching sha256 is not downloaded again. A listed file whose size differs from the state entry is downloaded to a new name (`<name>.v<N>`), and both are kept.
   - A re-run on an unchanged tree makes no downloads.
7. **Salted-hash logs.**
   - The run log never contains a path, incident name or URL in clear. It contains `sha256(salt + relative_path)[:16]`, the action and the HTTP status.
   - The salt comes from the environment variable `CR1_LOG_SALT`. The script refuses to run without it, and the salt is never written anywhere.
   - `state.json` holds clear relative paths and is NOT committed.
8. **Failures.**
   - Any 401 or 403, or a redirect to a login page, stops the whole run with "BLOCKED". There is no retry, no change of identity and no alternative path.
   - A 404 is logged and the run continues.
9. **Outputs.**
   - Downloaded files and `state.json` go under `--out`, which must be outside the repository.
   - Commit only derived summaries (counts by status), after custodian review.

## Not in scope

- Building perimeters from the IR. That is the builder, a separate job.
- IRWIN joins. Requirement 2: the incident-number key, or the 4 km / 3-day fallback, otherwise E8.
- Any pre-2027 season, and `/protected`.
