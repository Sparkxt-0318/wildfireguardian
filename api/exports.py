"""Exports of a checked route (GeoJSON, KML, CSV). Only ``checked_route`` results are exportable."""
from __future__ import annotations

import csv
import io
from xml.sax.saxutils import escape


def _iso_offset(input_time_iso: str, seconds) -> str:
    import datetime as dt
    t0 = dt.datetime.fromisoformat(input_time_iso.replace("Z", "+00:00"))
    return (t0 + dt.timedelta(seconds=float(seconds))).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_geojson(job: dict) -> dict:
    res = job["result"]
    route = res["route"]
    props = route["properties"]
    snap = job["snap"]
    common = {"job_id": job["job_id"], "verdict": res["verdict"], "policy": res.get("policy")}
    feats = [{"type": "Feature", "geometry": route["geometry"],
              "properties": dict(props, **common, arrival_s=res["arrival_s"], dwell_end_s=res["dwell_end_s"],
                                 lower_bound_L_s=res["lower_bound_L_s"], compute_s=res["compute_s"], exposure=res["exposure"])},
             {"type": "Feature", "geometry": {"type": "Point", "coordinates": [snap["start"]["lon"], snap["start"]["lat"]]},
              "properties": dict(common, role="start", node_id=snap["start"]["node_id"], time_s=res["departure_s"])},
             {"type": "Feature", "geometry": {"type": "Point", "coordinates": [snap["destination"]["lon"], snap["destination"]["lat"]]},
              "properties": dict(common, role="destination", node_id=snap["destination"]["node_id"], arrival_s=res["arrival_s"],
                                 dwell_end_s=res["dwell_end_s"])}]
    return {"type": "FeatureCollection", "features": feats, "provenance": res["provenance"]}


def to_csv(job: dict) -> str:
    res = job["result"]
    route = res["route"]
    p = route["properties"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["seq", "node_id", "lon", "lat", "time_s", "event"])
    waits_end = {(x["node_id"], x["to_s"]) for x in p.get("waits") or []}
    n = len(p["times_s"])
    for i, ((lon, lat), t, nid) in enumerate(zip(route["geometry"]["coordinates"], p["times_s"], p["node_ids"])):
        ev = "depart" if i == 0 else ("wait_end" if (nid, t) in waits_end and i > 0 and p["node_ids"][i - 1] == nid else ("arrive" if i == n - 1 else "pass"))
        w.writerow([i, nid, "%.7f" % lon, "%.7f" % lat, t, ev])
    w.writerow([n, p["node_ids"][-1], "%.7f" % route["geometry"]["coordinates"][-1][0], "%.7f" % route["geometry"]["coordinates"][-1][1],
                res["dwell_end_s"], "dwell_end"])
    prov = res["provenance"]
    buf.write("# verdict=%s job_id=%s package=%s %s kit=%s checkpoint=%s git_commit=%s\n" % (
        res["verdict"], job["job_id"], prov["package"], prov["package_version"], prov["kit"], prov["checkpoint"], prov["git_commit"]))
    return buf.getvalue()


def to_kml(job: dict) -> str:
    res = job["result"]
    route = res["route"]
    p = route["properties"]
    t0 = res["provenance"].get("input_time")
    coords = " ".join("%.7f,%.7f,0" % (lon, lat) for lon, lat in route["geometry"]["coordinates"])
    whens = "".join("<when>%s</when>" % _iso_offset(t0, t) for t in p["times_s"]) if t0 else ""
    gx = "".join("<gx:coord>%.7f %.7f 0</gx:coord>" % (lon, lat) for lon, lat in route["geometry"]["coordinates"]) if t0 else ""
    prov = res["provenance"]
    desc = escape("verdict=%s arrival_s=%s dwell_end_s=%s package=%s %s kit=%s checkpoint=%s git_commit=%s" % (
        res["verdict"], res["arrival_s"], res["dwell_end_s"], prov["package"], prov["package_version"], prov["kit"],
        prov["checkpoint"], prov["git_commit"]))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2"><Document>'
            "<name>WildfireGuardian checked route %s</name>" % escape(job["job_id"]) +
            "<Placemark><name>checked_route</name><description>%s</description>" % desc +
            "<LineString><tessellate>1</tessellate><coordinates>%s</coordinates></LineString></Placemark>" % coords +
            ("<Placemark><name>timed track</name><gx:Track>%s%s</gx:Track></Placemark>" % (whens, gx) if t0 else "") +
            "</Document></kml>\n")
