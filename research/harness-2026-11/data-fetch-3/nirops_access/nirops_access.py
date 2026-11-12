"""Allowlist-safe reads of the NIROPS 2020-2024 shapefile.

Rule (S-D9 A1 §1.2 and ACCESS_CONTROL): no attribute other than the incident ID, and no geometry, may be read for a
record whose Incident_C is not allowlisted. So:
  1. read the Incident_C column ALONE, for all records (the ID is the field the split may use);
  2. compute the fids whose Incident_C is allowlisted;
  3. read geometry and every other column BY FID, for those fids only.
No OGR attribute filter (`where=`) is used: a where-filter makes the driver read each record for evaluation.
"""
import pyogrio

ID_FIELD = 'Incident_C'


def id_index(shp):
    """fid -> Incident_C for all records. Reads the ID column only (no geometry, no other fields)."""
    df = pyogrio.read_dataframe(shp, columns=[ID_FIELD], read_geometry=False, fid_as_index=True)
    return df[ID_FIELD]


def allowlisted_fids(ids, allowed):
    allowed = set(allowed)
    return ids.index[ids.isin(allowed)].to_numpy()


def read_by_fid(shp, fids, ids, allowed, columns=None):
    """Read geometry and the attributes (all, or `columns`) for `fids`. Raises before any read if one of them is not allowlisted."""
    allowed = set(allowed)
    bad = [int(f) for f in fids if ids.loc[f] not in allowed]
    if bad:
        raise PermissionError(f'refused: {len(bad)} non-allowlisted fid(s) requested, e.g. fid {bad[0]}')
    if len(fids) == 0:
        raise ValueError('no fids requested')
    return pyogrio.read_dataframe(shp, fids=list(map(int, fids)), columns=columns, fid_as_index=True)


def read_incident(shp, incident, allowed, ids=None):
    """All features of one allowlisted incident, read by fid only."""
    if incident not in set(allowed):
        raise PermissionError(f'refused: {incident} is not allowlisted')
    ids = id_index(shp) if ids is None else ids
    fids = ids.index[ids == incident].to_numpy()
    return read_by_fid(shp, fids, ids, allowed)
