import L from "leaflet";
import { useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
} from "react-leaflet";
import {
  getFires,
  getRoute,
  getShelters,
  getSpread,
  type AppConfig,
  type Feature,
  type FiresCollection,
  type LineStringGeometry,
  type PathwayProps,
  type PolygonGeometry,
  type RouteResult,
  type Shelter,
  type Situation,
  type SpreadCollection,
  type SpreadPolygonProps,
} from "../api/client";
import { IconLocation, IconPhone } from "../components/Icons";
import { useI18n } from "../i18n";
import { formatKm } from "../lib/format";
import { getCurrentPosition, type Coords } from "../lib/geo";
import { arrowheadHtml } from "../svg/EvacArrow";
import { flamePulseHtml } from "../svg/FlamePulse";

const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTR = "&copy; OpenStreetMap contributors";

// ordinal spread ramp (validated with the dataviz validator, 1 h deepest)
const SPREAD_COLORS: Record<number, string> = {
  1: "#B91C1C",
  3: "#D64545",
  6: "#E98B8B",
};
const SPREAD_OPACITY: Record<string, number> = { likely: 0.4, possible: 0.22 };

function isPolygonFeature(
  f: Feature<PolygonGeometry | LineStringGeometry, SpreadPolygonProps | PathwayProps>,
): f is Feature<PolygonGeometry, SpreadPolygonProps> {
  return f.geometry.type === "Polygon";
}

function isPathwayFeature(
  f: Feature<PolygonGeometry | LineStringGeometry, SpreadPolygonProps | PathwayProps>,
): f is Feature<LineStringGeometry, PathwayProps> {
  return (
    f.geometry.type === "LineString" &&
    (f.properties as PathwayProps).kind === "pathway"
  );
}

const toLatLng = (c: [number, number]): [number, number] => [c[1], c[0]];

export function MapScreen({
  coords,
  onCoordsChange,
  situation,
  config,
  routeRequested,
}: {
  coords: Coords;
  onCoordsChange: (next: Coords) => void;
  situation: Situation | null;
  config: AppConfig | null;
  /** Home's GO button lands here with the route already requested. */
  routeRequested: boolean;
}) {
  const { t, pick, lang } = useI18n();
  const [map, setMap] = useState<L.Map | null>(null);
  const [fires, setFires] = useState<FiresCollection | null>(null);
  const [spread, setSpread] = useState<SpreadCollection | null>(null);
  const [shelters, setShelters] = useState<Shelter[]>([]);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [routeShown, setRouteShown] = useState(routeRequested);
  const [routeLoading, setRouteLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [legendOpen, setLegendOpen] = useState(true);

  // -- data layers, refreshed when the situation refreshes -------------------
  const generated = situation?.generated_utc ?? "";
  useEffect(() => {
    let alive = true;
    getFires()
      .then((d) => alive && setFires(d))
      .catch(() => alive && setFires(null));
    getSpread(coords.lat, coords.lon)
      .then((d) => alive && setSpread(d))
      .catch(() => alive && setSpread(null));
    getShelters(coords.lat, coords.lon)
      .then((d) => alive && setShelters(d))
      .catch(() => alive && setShelters([]));
    return () => {
      alive = false;
    };
  }, [coords.lat, coords.lon, generated]);

  // -- route -----------------------------------------------------------------
  useEffect(() => {
    if (routeRequested) setRouteShown(true);
  }, [routeRequested]);

  useEffect(() => {
    if (!routeShown) {
      setRoute(null);
      return;
    }
    let alive = true;
    setRouteLoading(true);
    getRoute(coords.lat, coords.lon)
      .then((r) => {
        if (alive) setRoute(r);
      })
      .catch(() => {
        if (alive) setNotice(t("error_title"));
      })
      .finally(() => {
        if (alive) setRouteLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeShown, coords.lat, coords.lon, generated]);

  // -- keep view on user when coords change ----------------------------------
  useEffect(() => {
    map?.setView([coords.lat, coords.lon]);
  }, [map, coords.lat, coords.lon]);

  // -- markers ---------------------------------------------------------------
  const flameIcon = useMemo(
    () =>
      L.divIcon({
        className: "wfg-flame-marker",
        html: flamePulseHtml(40),
        iconSize: [40, 40],
        iconAnchor: [20, 34],
      }),
    [],
  );

  const userIcon = useMemo(
    () =>
      L.divIcon({
        className: "wfg-user-marker",
        html:
          `<svg width="36" height="36" viewBox="0 0 36 36">` +
          `<circle cx="18" cy="18" r="10" fill="#1C5CAB" stroke="#FFFFFF" stroke-width="4"/>` +
          `<circle cx="18" cy="18" r="16" fill="none" stroke="#1C5CAB" stroke-width="2" opacity="0.4"/>` +
          `</svg>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      }),
    [],
  );

  const shelterIcon = useMemo(
    () =>
      L.divIcon({
        className: "wfg-shelter-marker",
        html:
          `<svg width="38" height="38" viewBox="0 0 38 38">` +
          `<circle cx="19" cy="19" r="17" fill="#1B7F4B" stroke="#FFFFFF" stroke-width="3"/>` +
          `<path d="M10 18 L19 10 L28 18" fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>` +
          `<path d="M12.5 17 V27 H25.5 V17" fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/>` +
          `</svg>`,
        iconSize: [38, 38],
        iconAnchor: [19, 19],
      }),
    [],
  );

  const walkerIcon = useMemo(
    () =>
      L.divIcon({
        className: "wfg-walker-marker",
        html:
          `<svg width="34" height="34" viewBox="0 0 24 24">` +
          `<circle cx="12" cy="12" r="11" fill="#1C5CAB"/>` +
          `<g stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none">` +
          `<circle cx="13.2" cy="5.6" r="1.6" fill="#FFFFFF" stroke="none"/>` +
          `<path d="M9 10 L12.4 8.4 L14.6 10.4 L17 11.2"/>` +
          `<path d="M12.4 8.4 L11.6 12.8 L14 15.2 L13.6 19"/>` +
          `<path d="M11.6 12.8 L8.8 14.8 L7 18.4"/>` +
          `</g></svg>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      }),
    [],
  );

  // -- layer data ------------------------------------------------------------
  const spreadPolys = useMemo(() => {
    if (!spread) return [];
    return spread.features
      .filter(isPolygonFeature)
      .sort((a, b) => b.properties.horizon_hours - a.properties.horizon_hours);
  }, [spread]);

  const pathways = useMemo(
    () => (spread ? spread.features.filter(isPathwayFeature) : []),
    [spread],
  );

  // -- interactions ----------------------------------------------------------
  const showNotice = (text: string) => {
    setNotice(text);
    window.setTimeout(() => setNotice(null), 8000);
  };

  const locateMe = async () => {
    try {
      const pos = await getCurrentPosition();
      onCoordsChange(pos);
    } catch {
      // graceful denial: default demo coordinate + visible bilingual notice
      onCoordsChange({ lat: 36.44, lon: 129.4 });
      showNotice(t("map_location_denied"));
    }
  };

  const tileUrl = config?.tile_url || OSM_TILES;
  const routeGeometry = route?.status === "ok" ? (route.geometry ?? null) : null;
  const routeShelter = route?.status === "ok" ? (route.shelter ?? null) : null;

  return (
    <div className="map-wrap">
      <MapContainer
        center={[coords.lat, coords.lon]}
        zoom={12}
        zoomControl={false}
        ref={setMap}
        attributionControl={true}
      >
        <TileLayer url={tileUrl} attribution={OSM_ATTR} />

        {/* spread polygons, 6h → 1h so the deepest sits on top */}
        {spreadPolys.map((f, i) => (
          <Polygon
            key={`sp-${i}`}
            positions={f.geometry.coordinates.map((ring) => ring.map(toLatLng))}
            pathOptions={{
              color: SPREAD_COLORS[f.properties.horizon_hours] ?? "#D64545",
              weight: 1.5,
              fillColor: SPREAD_COLORS[f.properties.horizon_hours] ?? "#D64545",
              fillOpacity: SPREAD_OPACITY[f.properties.p_level] ?? 0.25,
            }}
          />
        ))}

        {/* animated dashed pathway arrows */}
        {pathways.map((f, i) => (
          <Polyline
            key={`pwl-${i}`}
            positions={f.geometry.coordinates.map(toLatLng)}
            pathOptions={{
              color: "#B91C1C",
              weight: 4,
              className: "wfg-pathway",
            }}
          />
        ))}
        {pathways.map((f, i) => {
          const pts = f.geometry.coordinates;
          if (pts.length === 0) return null;
          const tip = toLatLng(pts[pts.length - 1]);
          return (
            <Marker
              key={`pwa-${i}`}
              position={tip}
              icon={L.divIcon({
                className: "wfg-arrowhead-marker",
                html: arrowheadHtml(f.properties.bearing_deg),
                iconSize: [26, 26],
                iconAnchor: [13, 13],
              })}
              interactive={false}
            />
          );
        })}

        {/* fire detections — pulsing flame markers */}
        {fires?.features.map((f, i) => (
          <Marker
            key={`fire-${i}`}
            position={toLatLng(f.geometry.coordinates)}
            icon={flameIcon}
            interactive={false}
          />
        ))}

        {/* evacuation route — thick blue line + walking figure */}
        {routeGeometry && (
          <>
            <Polyline
              positions={routeGeometry.coordinates.map(toLatLng)}
              pathOptions={{
                color: "#1C5CAB",
                weight: 8,
                className: "wfg-route-line",
              }}
            />
            {routeGeometry.coordinates.length > 0 && (
              <Marker
                position={toLatLng(routeGeometry.coordinates[0])}
                icon={walkerIcon}
                interactive={false}
              />
            )}
          </>
        )}

        {/* shelters */}
        {shelters.map((s, i) => (
          <Marker key={`sh-${i}`} position={[s.lat, s.lon]} icon={shelterIcon}>
            <Popup>
              <strong>{lang === "ko" ? s.name_ko : s.name_en}</strong>
              <br />
              {t("dist_label")}: {formatKm(s.distance_km)} {t("unit_km")}
              <br />
              {t("walk_label")}: {s.walk_minutes} {t("unit_min")}
            </Popup>
          </Marker>
        ))}

        {/* user */}
        <Marker position={[coords.lat, coords.lon]} icon={userIcon} interactive={false} />
      </MapContainer>

      {/* oversized zoom controls */}
      <div className="map-controls">
        <button
          type="button"
          className="map-btn"
          aria-label={t("map_zoom_in")}
          onClick={() => map?.zoomIn()}
        >
          +
        </button>
        <button
          type="button"
          className="map-btn"
          aria-label={t("map_zoom_out")}
          onClick={() => map?.zoomOut()}
        >
          −
        </button>
      </div>

      {/* my location */}
      <button type="button" className="map-mylocation" onClick={locateMe}>
        <IconLocation size={26} />
        {t("map_my_location")}
      </button>

      {/* legend: words + swatches (spec §7), collapsible for small screens */}
      {legendOpen ? (
        <div className="map-legend">
          <button
            type="button"
            onClick={() => setLegendOpen(false)}
            style={{
              border: "none",
              background: "none",
              padding: 0,
              width: "100%",
              textAlign: "left",
              cursor: "pointer",
            }}
          >
            <h3>{t("legend_title")} ✕</h3>
          </button>
          <div className="legend-row">
            <span
              className="swatch"
              style={{ background: "#E25822", borderRadius: "50%" }}
            />
            {t("legend_fire")}
          </div>
          <div className="legend-row">
            <span className="swatch" style={{ background: "#B91C1C" }} />
            {t("legend_spread_1h")}
          </div>
          <div className="legend-row">
            <span className="swatch" style={{ background: "#D64545" }} />
            {t("legend_spread_3h")}
          </div>
          <div className="legend-row">
            <span className="swatch" style={{ background: "#E98B8B" }} />
            {t("legend_spread_6h")}
          </div>
          <div className="legend-row">
            <span
              className="swatch line"
              style={{
                background:
                  "repeating-linear-gradient(90deg,#B91C1C 0 6px,transparent 6px 12px)",
              }}
            />
            {t("legend_pathway")}
          </div>
          <div className="legend-row">
            <span
              className="swatch"
              style={{ background: "#1B7F4B", borderRadius: "50%" }}
            />
            {t("legend_shelter")}
          </div>
          <div className="legend-row">
            <span
              className="swatch"
              style={{ background: "#1C5CAB", borderRadius: "50%" }}
            />
            {t("legend_me")}
          </div>
          <div className="legend-row">
            <span className="swatch line" style={{ background: "#1C5CAB" }} />
            {t("legend_route")}
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="map-mylocation"
          style={{ top: 84 }}
          onClick={() => setLegendOpen(true)}
        >
          {t("legend_title")}
        </button>
      )}

      {/* route action — the screen's one primary button */}
      <div className="map-route-btn">
        {route?.status === "no_safe_walk" ? (
          <a className="btn-giant level-GO" href="tel:119">
            <IconPhone size={32} />
            {t("call_119")}
          </a>
        ) : (
          <button
            type="button"
            className={`btn-giant level-${situation?.danger.level ?? "SAFE"}`}
            onClick={() => setRouteShown(!routeShown)}
          >
            {routeLoading
              ? `${t("map_route_loading")}…`
              : routeShown
                ? t("map_route_hide")
                : t("map_route_btn")}
          </button>
        )}
      </div>

      {/* honest route outcomes + location notices */}
      {route?.status === "no_safe_walk" && (
        <div className="map-notice" role="alert">
          {t("route_no_safe_walk")}
          {route.warnings_ko.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {(lang === "ko" ? route.warnings_ko : route.warnings_en).join(" ")}
            </div>
          )}
        </div>
      )}
      {route?.status === "outside_region" && (
        <div className="map-notice" role="alert">
          {t("route_outside_region")}
        </div>
      )}
      {route?.status === "ok" && routeShelter && (
        <div className="map-notice" style={{ borderColor: "var(--safe)" }}>
          <strong>{pick(routeShelter, "name")}</strong>
          {" · "}
          {t("dist_label")}: {formatKm(routeShelter.distance_km)} {t("unit_km")}
          {" · "}
          {t("walk_label")}: {routeShelter.walk_minutes} {t("unit_min")}
          {(lang === "ko" ? route!.warnings_ko : route!.warnings_en).map(
            (w, i) => (
              <div key={i} style={{ marginTop: 6 }}>
                {w}
              </div>
            ),
          )}
        </div>
      )}
      {notice && (
        <div className="map-notice" role="alert">
          {notice}
        </div>
      )}
    </div>
  );
}
