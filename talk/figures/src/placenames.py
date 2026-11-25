"""Korean place names in Hangul, read from the committed planner data (never transliterated from the romanised form).

  * villages and shelters: places.geojson, property `name` (the OpenStreetMap `name` tag, Hangul);
  * the case label: regions/index.json, `name.ko` of the region (의성·안동 for uiseong_andong_2025).

If a place has no Hangul name in the data, `ko()` returns the romanised name when there is one (else None) and adds the
place to MISSING, which the figure scripts write to NEEDS.md through `record_missing()`.
"""
import json
import re

from prov import git_show

PLACES = "planner/public/data/regions/uiseong_andong_2025/places.geojson"
REGIONS = "planner/public/data/regions/index.json"
REGION_ID = "uiseong_andong_2025"
HANGUL = re.compile("[가-힣ᄀ-ᇿ㄰-㆏]")

_places = None
MISSING = {}


def _load():
    global _places
    if _places is None:
        _places = {f["properties"]["id"]: f["properties"] for f in json.loads(git_show(PLACES))["features"]}
    return _places


def place(pid):
    return _load()[pid]


def ko(pid):
    """Hangul name of a place id; the romanised name (or None) when the data has no Hangul name."""
    p = place(pid)
    if p.get("name") and HANGUL.search(p["name"]):
        return p["name"]
    MISSING[pid] = {"category": p["category"], "role": p["role"], "name_en": p.get("name_en"),
                    "osm_tags": p.get("osm", {}).get("tags")}
    return p.get("name_en")


def by_entry_node(node, role="destination"):
    """The one place of `role` whose road entry is `node` (raises if not exactly one)."""
    hits = [pid for pid, p in _load().items() if p["role"] == role and p["entry"]["node"] == node]
    if len(hits) != 1:
        raise ValueError(f"{len(hits)} {role} places enter the road graph at {node}")
    return hits[0]


def region_ko(region_id=REGION_ID):
    r = [r for r in json.loads(git_show(REGIONS)) if r["region_id"] == region_id][0]
    if not HANGUL.search(r["name"].get("ko") or ""):
        MISSING[f"region:{region_id}"] = {"name_en": r["name"].get("en")}
        return r["name"]["en"]
    return r["name"]["ko"]


def ledger_rows(L, ids, region=True):
    """One SOURCES row per name shown."""
    for pid in ids:
        p = place(pid)
        L.add(f"Place name ({p['category']})", ko(pid), file=PLACES, field=f"features[id={pid}].properties.name",
              shown=ko(pid), note=f"romanised name_en: {p.get('name_en')}" if p.get("name_en") else
              "no romanised name in the data")
    if region:
        L.add("Case label (region name)", region_ko(), file=REGIONS, field=f"[region_id={REGION_ID}].name.ko",
              shown=region_ko())


def record_missing(fig_name):
    """Write the places shown without a Hangul name (for NEEDS.md) to check/{fig_name}_names_missing.json."""
    from style import CHECK
    (CHECK / f"{fig_name}_names_missing.json").write_text(json.dumps(MISSING, indent=1, ensure_ascii=False))
    if MISSING:
        print(f"{fig_name}: no Hangul name in the data for {list(MISSING)} (NEEDS.md)")
