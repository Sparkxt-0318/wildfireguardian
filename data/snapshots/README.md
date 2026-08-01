# `data/snapshots/` — immutable evidence store

Round-3 PHASE 1-B. Created because Round 2 lost the inputs behind a committed result.

## The problem this solves

`data/cache/**` and `data/raw/**` are git-ignored (`.gitignore:60,62`). That is
correct for a *cache* — it is a performance artifact and is allowed to vanish.
It is wrong for *evidence*. In Round 2 the OSMnx graph cache was regenerated
after a run had already been committed, so the network that produced the
published numbers no longer existed anywhere: not on disk, not in git.

A snapshot is the other thing. It is content-addressed, immutable, hashed, and
committed.

## Naming

```
{source}_{region}_{YYYYMMDD}_{hash8}.{ext}
```

* `source`, `region` — normalised so `_` never appears **inside** a field
  (`osm-walk`, `yeongdeok-2025`). Splitting the stem on `_` therefore always
  yields exactly four fields.
* `YYYYMMDD` — the **acquisition** date, read from the source file's mtime, not
  the date the snapshot was taken. A snapshot made today of a file fetched last
  week records last week.
* `hash8` — first 8 hex chars of the file's sha256.

Every snapshot has a sibling `.sha256` in standard `shasum -a 256` format, so
integrity is checkable with no project code:

```bash
cd data/snapshots && shasum -a 256 -c osm-shelters_*.sha256
```

## Compression — a storage decision, never an identity one

`.graphml` payloads over 1 MiB are stored gzipped. **The `hash8` in the filename
and the digest in the `.sha256` sidecar are always the digest of the
*uncompressed* bytes** — the thing that was actually acquired. Compression can
therefore be changed, or dropped entirely, without any snapshot changing identity.

The gzip stream is written with `mtime=0` and level 9, so the same input always
produces byte-identical output and re-running the tool stays a no-op.

```bash
gunzip -c osm-walk_*.graphml.gz | shasum -a 256   # == the .sha256 sidecar
```

`MANIFEST.json` additionally carries `stored_file` / `stored_bytes` /
`stored_sha256` describing the on-disk artifact.

| | uncompressed | stored |
|---|---:|---:|
| `osm-walk_…2bff8d85.graphml` | 12,061,393 B | 1,746,538 B (14.5 %) |
| `osm-drive_…f537bdf5.graphml` | 3,233,194 B | 601,218 B (18.6 %) |

## What is and is not committed

Committed (≈ 2.28 MB): both `.graphml.gz`, all three `.geojson`, **every**
`.sha256`, `MANIFEST.json`, this file.

Not committed: `osm-httpcache_*` payloads (≈ 24 MB of raw Overpass responses).
They are fully derivable from the committed graphs, so they add bulk without
adding reproducibility. Their **digests remain in `MANIFEST.json`** and their
`.sha256` sidecars **are** committed, so a future fetch can still be compared
byte-for-byte against what Round 2 actually received. Manifest entries carry
`committed_to_git: false`; `--verify` reports them as `absent`, not as failures,
when running from a fresh clone.

## Rules

1. **Never overwrite.** Same bytes → same name → re-running is a no-op.
   Different bytes → a new file. `snapshot_external.py` refuses to overwrite and
   raises on a name/content mismatch.
2. **Identical content is stored once.** Two source paths with the same bytes
   collapse to one snapshot (this is why `_httpcache` yields 7 files, not 8).
3. **`MANIFEST.json` is the index**: digest, byte size, acquisition time, origin
   path, acquisition parameters, `config_hash`, and `git_commit` per entry.

## Usage

```bash
python scripts/snapshot_external.py --preset osm --include-httpcache
python scripts/snapshot_external.py --verify
python scripts/snapshot_external.py FILE --source firms --region yeongdeok-2025
```

## ⚠ Provenance warning on the current OSM snapshots

The OSM snapshots here are dated **2026-07-24**. The committed
`data/processed/real_roads_real_hazard.json` (the 459-origin run) was written
**2026-07-23 20:54**, roughly 25 hours *earlier*, and its node/edge counts do
not match this graph:

| | committed 459-origin run | snapshot `osm-walk_…2bff8d85` |
|---|---|---|
| walk nodes | 8439 | 8443 |
| walk edges (collapsed) | 11015 | 11020 |

These snapshots are therefore **the current OSM state, not the inputs to the
committed Round-2 numbers**. The Jul-23 graph was never committed and has been
overwritten; it is unrecoverable. This store exists so that this cannot happen
again — it does not retroactively fix Round 2.

Any re-run compared against the committed 459-origin figures is comparing across
*two* changes (network drift **and** whatever was intentionally changed). Say so
explicitly when reporting such a comparison.
