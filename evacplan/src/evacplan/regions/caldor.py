"""US region 1: the Caldor Fire 2021, South Lake Tahoe. Instance builder.

Pipeline (every assumption in ``docs/ASSUMPTIONS.md``, section "Real US region 1"):

1. roads: OSM drivable roads of :attr:`CaldorConfig.bbox_lonlat` through osmnx (a GraphML file,
   or a download from the Overpass API with ``online``) -> :func:`evacplan.regions.osm.to_road_graph`;
2. facilities: the CMS nursing-home provider file (a file, or a download from data.cms.gov),
   providers in CA and NV, located by the file's own coordinates or a geocodes CSV or the Census
   geocoder, kept inside the bbox and snapped to the nearest road node;
3. residents: CMS average daily census (else occupancy x certified beds), SYNTHETIC mobility mix;
4. shelters: a JSON list of receiving sites, else SYNTHETIC safe-zone exits (major-road nodes at
   the safe sides of the road graph);
5. fleet: SYNTHETIC (facility vans + a mutual-aid pool of buses and ambulances at the first exit);
6. fire: timestamped perimeters (GeoJSON) -> ``hazard_contract.from_perimeters`` on a 375 m grid
   covering the roads.

Status on the cloud container (2026-10-31): **BLOCKED**. The repo has no Caldor road graph,
facilities or perimeters (the sealed study lives on Siyeong's Mac) and the OSM, CMS and geocoder
hosts are blocked. :func:`requirements` lists exactly what is needed; the builder never
substitutes synthetic data for the real inputs.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import hazard_contract as hc

from ..schema import Budgets, ClassCounts, ClassDurations, Facility, HazardRef, Instance, Shelter, save_instance
from . import BuildBlocked, Missing
from .cms import CMS_DATASET_ID, CMS_HOST, download_provider_file, read_provider_file, select
from .geocode import CENSUS_HOST, Geocode, geocode_census, read_geocodes_csv, write_geocodes_csv
from .osm import ATTRIBUTION, MAJOR_HIGHWAYS, OSM_HOST, download_drive_graph, load_graph_file, nearest_node, \
    to_road_graph, with_waitable
from .people import FleetRule, boarding_times, residents_for, synthetic_fleet, unloading_times
from .perimeters import PERSIST_S, grid_for, hazard_from_perimeters, read_perimeter_geojson

REGION_ID = "US1-caldor-2021-slt"
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "caldor"     # git-ignored downloads
NIROPS_DOI = "10.17632/95rj5d379g.1"


@dataclass(frozen=True)
class CaldorConfig:
    region_id: str = REGION_ID
    bbox_lonlat: tuple[float, float, float, float] = (-120.15, 38.70, -119.70, 39.12)   # west, south, east, north
    crs_epsg: int = 3310                                  # NAD83 / California Albers (the sealed study's CRS)
    states: tuple[str, ...] = ("CA", "NV")
    issue_time_utc: str = "2021-08-30T18:00:00Z"          # to confirm: the South Lake Tahoe order, 30 Aug 2021
    cell_m: float = 375.0
    margin_cells: int = 3
    K: int = 4
    perimeter_mode: str = "stratified"
    perimeter_time_property: str = "time"
    burn_persist_s: float = PERSIST_S
    speed: str = "fixed"
    speed_kmh: float = 40.0
    occupancy: float = 0.75
    release_s: float = 0.0
    max_snap_m: float = 500.0
    exit_sides: tuple[str, ...] = ("east", "north")      # the safe sides (the fire came from the south-west)
    exit_band_m: float = 2000.0
    peak_kw_m2: float = 10.0
    dose_kj_m2: float = 100.0
    fleet: FleetRule = field(default_factory=FleetRule)
    synthetic_hazard: bool = False                        # True only for test fixtures


@dataclass(frozen=True)
class CaldorInputs:
    graph: Path | None = None          # GraphML (osmnx.save_graphml) or OSM XML of the bbox's drivable roads
    cms: Path | None = None            # NH_ProviderInfo_<MonYYYY>.csv
    geocodes: Path | None = None       # CSV ccn,lat,lon[,source]
    perimeters: Path | None = None     # GeoJSON of timestamped perimeters
    shelters: Path | None = None       # JSON list of receiving sites (default: SYNTHETIC safe-zone exits)
    online: bool = False               # download what is not given (needs the hosts)


def requirements(cfg: CaldorConfig = CaldorConfig()) -> list[Missing]:
    """Everything the build needs, with the hosts that provide it or the files that replace them."""
    w, s, e, n = cfg.bbox_lonlat
    return [
        Missing("OSM road graph (drivable roads)",
                f"host {OSM_HOST} (osmnx, --online), or --graph FILE.graphml saved with osmnx.save_graphml("
                f"osmnx.graph_from_bbox(bbox=({w}, {s}, {e}, {n}), network_type='drive'))"),
        Missing("CMS nursing-home provider file",
                f"host {CMS_HOST} (Provider Data Catalog dataset {CMS_DATASET_ID}, --online), or --cms "
                "NH_ProviderInfo_<MonYYYY>.csv"),
        Missing("facility coordinates",
                f"host {CENSUS_HOST} (Census batch geocoder, --online), or --geocodes CSV (ccn,lat,lon); not "
                "needed when the CMS file carries Latitude/Longitude"),
        Missing("Caldor fire perimeters",
                "--perimeters GeoJSON of timestamped perimeters spanning the issue time to the planning horizon "
                f"(about 2021-08-29 to 2021-08-31), e.g. NIROPS IR perimeters (data.mendeley.com, DOI {NIROPS_DOI}; "
                "the 1.39 GB NIROPS_2020_2024_R1_R6.zip is on Siyeong's Mac) or the NIFC/WFIGS perimeter history"),
    ]


def check_inputs(inputs: CaldorInputs, cfg: CaldorConfig = CaldorConfig()) -> list[Missing]:
    """What is missing before any download is attempted."""
    req = {m.item: m for m in requirements(cfg)}
    out: list[Missing] = []
    for item, path, downloadable in (("OSM road graph (drivable roads)", inputs.graph, True),
                                     ("CMS nursing-home provider file", inputs.cms, True),
                                     ("Caldor fire perimeters", inputs.perimeters, False)):
        if path is not None and not Path(path).is_file():
            out.append(Missing(item, f"file not found: {path}"))
        elif path is None and not (downloadable and inputs.online):
            out.append(req[item])
    if inputs.geocodes is not None and not Path(inputs.geocodes).is_file():
        out.append(Missing("facility coordinates", f"file not found: {inputs.geocodes}"))
    elif inputs.geocodes is None and inputs.cms is None and not inputs.online:
        out.append(req["facility coordinates"])     # unknown until the CMS file is read
    if inputs.shelters is not None and not Path(inputs.shelters).is_file():
        out.append(Missing("receiving sites", f"file not found: {inputs.shelters}"))
    return out


@dataclass
class BuiltRegion:
    instance: Instance
    hazard: hc.ScenarioSet
    report: dict[str, Any]

    def write(self, folder, *, overwrite: bool = False) -> Path:
        folder = Path(folder)
        self.hazard.write(folder / self.instance.hazard.scenario_set, overwrite=overwrite)
        save_instance(self.instance, folder / "instance.json", overwrite=overwrite)
        (folder / "build_report.json").write_text(json.dumps(self.report, indent=1, default=str) + "\n")
        return folder


def _exits(roads, highway: dict[str, str], cfg: CaldorConfig) -> list[str]:
    """SYNTHETIC safe-zone exits: one major-road node at each safe side of the road graph."""
    xy = {n.id: (n.x, n.y) for n in roads.nodes}
    major = set()
    for e in roads.edges:
        if set(highway.get(e.id, "").split(",")) & MAJOR_HIGHWAYS:
            major.update((e.u, e.v))
    xs = [p[0] for p in xy.values()]
    ys = [p[1] for p in xy.values()]
    picks: list[str] = []
    for side in cfg.exit_sides:
        if side == "east":
            cand = [i for i in major if xy[i][0] >= max(xs) - cfg.exit_band_m]
            key = (lambda i: (xy[i][0], i))
        elif side == "north":
            cand = [i for i in major if xy[i][1] >= max(ys) - cfg.exit_band_m]
            key = (lambda i: (xy[i][1], i))
        elif side == "west":
            cand = [i for i in major if xy[i][0] <= min(xs) + cfg.exit_band_m]
            key = (lambda i: (-xy[i][0], i))
        elif side == "south":
            cand = [i for i in major if xy[i][1] <= min(ys) + cfg.exit_band_m]
            key = (lambda i: (-xy[i][1], i))
        else:
            raise ValueError(f"unknown exit side {side!r}")
        cand = [i for i in cand if i not in picks]
        if cand:
            picks.append(max(cand, key=key))
    return picks


def build(inputs: CaldorInputs, cfg: CaldorConfig = CaldorConfig(), *, work_dir: Path | None = None) -> BuiltRegion:
    """Build the instance and its scenario set. Raises :class:`BuildBlocked` naming what is missing."""
    from pyproj import Transformer
    missing = check_inputs(inputs, cfg)
    if missing:
        raise BuildBlocked(missing, cfg.region_id)
    work = Path(work_dir) if work_dir else DATA_DIR
    report: dict[str, Any] = {"region": cfg.region_id, "config": {k: v for k, v in cfg.__dict__.items()
                                                                  if k != "fleet"} | {"fleet": cfg.fleet.__dict__}}

    # 1. roads
    G = load_graph_file(inputs.graph) if inputs.graph else download_drive_graph(cfg.bbox_lonlat)
    roads, info = to_road_graph(G, crs_epsg=cfg.crs_epsg, speed_kmh=cfg.speed_kmh, speed=cfg.speed,
                                provenance={"region": cfg.region_id, "bbox_lonlat": list(cfg.bbox_lonlat),
                                            "file": str(inputs.graph) if inputs.graph else "downloaded"})
    report["roads"] = {"nodes": len(roads.nodes), "edges": len(roads.edges), **{k: v for k, v in info.items()
                                                                                  if k != "highway"}}

    # 2. facilities
    cms_path = inputs.cms or download_provider_file(work / "cms" / "NH_ProviderInfo.csv")
    facs = select(read_provider_file(cms_path), states=cfg.states)
    geocodes: dict[str, Geocode] = read_geocodes_csv(inputs.geocodes) if inputs.geocodes else {}
    need = [f for f in facs if (f.lat is None or f.lon is None) and f.ccn not in geocodes]
    failed: dict[str, str] = {}
    if need:
        if not inputs.online:
            raise BuildBlocked([Missing("facility coordinates", f"the CMS file has no coordinates for {len(need)} "
                                        f"providers in {cfg.states}: host {CENSUS_HOST} (--online) or --geocodes CSV "
                                        "(ccn,lat,lon) for CCNs " + ", ".join(f.ccn for f in need[:20]))], cfg.region_id)
        got, failed = geocode_census(need)
        geocodes.update(got)
        write_geocodes_csv(work / "geocodes.csv", geocodes)
    w, s, e, n = cfg.bbox_lonlat
    to_xy = Transformer.from_crs("EPSG:4326", f"EPSG:{cfg.crs_epsg}", always_xy=True)
    facilities: list[Facility] = []
    fac_report = []
    for f in facs:
        if f.lat is not None and f.lon is not None:
            lat, lon, src = f.lat, f.lon, "cms"
        elif f.ccn in geocodes:
            g = geocodes[f.ccn]
            lat, lon, src = g.lat, g.lon, g.source
        else:
            fac_report.append({"ccn": f.ccn, "name": f.name, "kept": False, "why": failed.get(f.ccn, "not geocoded")})
            continue
        if not (w <= lon <= e and s <= lat <= n):
            continue
        x, y = to_xy.transform(lon, lat)
        node, dist = nearest_node(roads, x, y)
        if dist > cfg.max_snap_m:
            fac_report.append({"ccn": f.ccn, "name": f.name, "kept": False, "why": f"{dist:.0f} m from the roads"})
            continue
        counts, census_src = residents_for(f, occupancy=cfg.occupancy)
        if counts.total == 0:
            fac_report.append({"ccn": f.ccn, "name": f.name, "kept": False, "why": census_src})
            continue
        facilities.append(Facility(id=f"CMS-{f.ccn}", node=node, residents=counts, boarding_s=boarding_times(),
                                   release_s=cfg.release_s, name=f.name))
        fac_report.append({"ccn": f.ccn, "name": f.name, "kept": True, "coords": src, "snap_m": round(dist, 1),
                           "residents": counts.vector(), "census": census_src, "beds": f.certified_beds})
    if not facilities:
        raise ValueError(f"no CMS provider in {cfg.states} lies inside the bbox {cfg.bbox_lonlat}")
    report["facilities"] = fac_report

    # 3. shelters
    synthetic_shelters = inputs.shelters is None
    if synthetic_shelters:
        exits = _exits(roads, info["highway"], cfg)
        if not exits:
            raise ValueError("no major-road exit on the safe sides; pass --shelters")
        big = ClassCounts(ambulatory=100_000, wheelchair=100_000, bedbound=100_000)
        shelters = [Shelter(id=f"EXIT{i + 1}", node=node, capacity=big, open_windows=[(0.0, cfg.burn_persist_s)],
                            unloading_s=unloading_times(), name=f"SYNTHETIC safe-zone exit {i + 1} ({side})")
                    for i, (node, side) in enumerate(zip(exits, cfg.exit_sides))]
    else:
        shelters = []
        for i, sdef in enumerate(json.loads(Path(inputs.shelters).read_text())):
            x, y = to_xy.transform(float(sdef["lon"]), float(sdef["lat"]))
            node, dist = nearest_node(roads, x, y)
            un = sdef.get("unloading_s")
            shelters.append(Shelter(
                id=str(sdef.get("id", f"S{i + 1}")), node=node, capacity=ClassCounts.of(sdef["capacity"]),
                open_windows=[tuple(wd) for wd in sdef.get("open_windows", [[0.0, cfg.burn_persist_s]])],
                unloading_s=unloading_times() if un is None else ClassDurations(ambulatory=un[0], wheelchair=un[1],
                                                                                 bedbound=un[2]),
                name=str(sdef.get("name", ""))))
    report["shelters"] = [{"id": sh.id, "node": sh.node, "name": sh.name} for sh in shelters]

    # 4. fleet (SYNTHETIC)
    totals = tuple(sum(f.residents.vector()[c] for f in facilities) for c in range(3))
    vehicles = synthetic_fleet([f.node for f in facilities], totals, shelters[0].node, cfg.fleet)
    report["fleet"] = {"vehicles": len(vehicles), "staging_node": shelters[0].node, "residents_by_class": totals}

    # 5. fire
    series = read_perimeter_geojson(inputs.perimeters, time_property=cfg.perimeter_time_property,
                                    crs_epsg=cfg.crs_epsg)
    xs = [nd.x for nd in roads.nodes]
    ys = [nd.y for nd in roads.nodes]
    transform, height, width = grid_for((min(xs), min(ys), max(xs), max(ys)), cfg.cell_m, cfg.margin_cells)
    hazard = hazard_from_perimeters(series, transform=transform, height=height, width=width, crs_epsg=cfg.crs_epsg,
                                    issue_time_utc=cfg.issue_time_utc, K=cfg.K, mode=cfg.perimeter_mode,
                                    burn_duration_s=cfg.burn_persist_s, synthetic=cfg.synthetic_hazard)
    report["hazard"] = {"perimeters": [t.isoformat() for t, _ in series], "grid": [height, width],
                        "horizon_s": hazard.meta.horizon_s, "K": hazard.K, "mode": cfg.perimeter_mode}

    sites = [f.node for f in facilities] + [sh.node for sh in shelters] + [v.depot for v in vehicles]
    roads = with_waitable(roads, sites)
    parts = ["residents' mobility", "fleet"] + (["shelters"] if synthetic_shelters else [])
    instance = Instance(
        name=f"{cfg.region_id} [SYNTHETIC {', '.join(parts)}]", synthetic=True, graph=roads,
        facilities=facilities, vehicles=vehicles, shelters=shelters,
        hazard=HazardRef(scenario_set="hazard", t0_offset_s=0.0,
                         budgets=Budgets(peak_kw_m2=cfg.peak_kw_m2, dose_kj_m2=cfg.dose_kj_m2)),
        provenance={
            "label": "SYNTHETIC (" + ", ".join(parts) + "); roads, facilities and fire perimeters are real data",
            "region": cfg.region_id, "builder": "evacplan.regions.caldor", "attribution": ATTRIBUTION,
            "sources": {"roads": "OpenStreetMap via osmnx", "facilities": f"CMS Provider Data Catalog {CMS_DATASET_ID}",
                        "fire": "observed perimeters via hazard_contract.from_perimeters"},
            "assumptions": "evacplan/docs/ASSUMPTIONS.md (Real US region 1)",
        },
    )
    return BuiltRegion(instance=instance, hazard=hazard, report=report)


# ---------------------------------------------------------------------------------- CLI
def add_arguments(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--out", type=Path, default=None, help="write instance.json + hazard/ here")
    ap.add_argument("--graph", type=Path, default=None, help="GraphML (osmnx) or OSM XML of the drivable roads")
    ap.add_argument("--cms", type=Path, default=None, help="CMS NH_ProviderInfo CSV")
    ap.add_argument("--geocodes", type=Path, default=None, help="CSV ccn,lat,lon")
    ap.add_argument("--perimeters", type=Path, default=None, help="GeoJSON of timestamped perimeters")
    ap.add_argument("--shelters", type=Path, default=None, help="JSON receiving sites (default: SYNTHETIC exits)")
    ap.add_argument("--issue-time", default=CaldorConfig.issue_time_utc, help="hazard issue time (UTC, ISO 8601)")
    ap.add_argument("--online", action="store_true", help="download roads, CMS file and geocodes (needs the hosts)")


def cli_main(args) -> int:
    inputs = CaldorInputs(graph=args.graph, cms=args.cms, geocodes=args.geocodes, perimeters=args.perimeters,
                          shelters=args.shelters, online=args.online)
    cfg = CaldorConfig(issue_time_utc=args.issue_time)
    try:
        built = build(inputs, cfg)
    except BuildBlocked as exc:
        print(exc.report())
        print("  (alternative: the sealed Caldor study's graph.json and hazard packets on Siyeong's Mac, through "
              "evacplan.adapters.wfg_graph.from_wfg_graph and hazard_contract.from_wfg_packet)")
        return 2
    if args.out is None:
        print(json.dumps(built.report, indent=1, default=str))
        return 0
    built.write(args.out)
    print(f"{built.instance.name}: {len(built.instance.facilities)} facilities, {built.instance.residents_total} "
          f"residents, {len(built.instance.vehicles)} vehicles -> {args.out}")
    return 0
