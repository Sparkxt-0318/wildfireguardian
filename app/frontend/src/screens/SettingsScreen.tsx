import { useState } from "react";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import type { AppConfig, Situation } from "../api/client";
import { LangToggle } from "../components/LangToggle";
import { IconLocation } from "../components/Icons";
import { useI18n } from "../i18n";
import { getCurrentPosition, type Coords } from "../lib/geo";
import {
  applyTextScale,
  getPref,
  setPref,
  type HomeLocation,
} from "../lib/prefs";

const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTR = "&copy; OpenStreetMap contributors";

const pickIcon = L.divIcon({
  className: "wfg-user-marker",
  html:
    `<svg width="36" height="36" viewBox="0 0 36 36">` +
    `<circle cx="18" cy="18" r="10" fill="#1B7F4B" stroke="#FFFFFF" stroke-width="4"/>` +
    `</svg>`,
  iconSize: [36, 36],
  iconAnchor: [18, 18],
});

function PickHandler({ onPick }: { onPick: (c: Coords) => void }) {
  useMapEvents({
    click: (e) => onPick({ lat: e.latlng.lat, lon: e.latlng.lng }),
  });
  return null;
}

/**
 * Settings: text size (×1.0 / ×1.25 via root font-size), language, home
 * location (use-my-location or map pick), about + full disclaimer.
 */
export function SettingsScreen({
  config,
  situation,
  home,
  onHomeChange,
}: {
  config: AppConfig | null;
  situation: Situation | null;
  home: HomeLocation | null;
  onHomeChange: (home: HomeLocation) => void;
}) {
  const { t, pick } = useI18n();
  const [scale, setScale] = useState<1 | 1.25>(
    () => getPref("textScale") ?? 1,
  );
  const [picking, setPicking] = useState(false);
  const [pickPos, setPickPos] = useState<Coords | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const setTextScale = (next: 1 | 1.25) => {
    setScale(next);
    setPref("textScale", next);
    applyTextScale(next);
  };

  const useMyLocation = async () => {
    try {
      const pos = await getCurrentPosition();
      onHomeChange({ ...pos, label: t("map_my_location") });
      setNotice(t("saved"));
    } catch {
      setNotice(t("map_location_denied"));
    }
    window.setTimeout(() => setNotice(null), 6000);
  };

  const savePicked = () => {
    if (!pickPos) return;
    onHomeChange({ ...pickPos, label: t("pick_on_map") });
    setPicking(false);
    setPickPos(null);
    setNotice(t("saved"));
    window.setTimeout(() => setNotice(null), 6000);
  };

  const mapCenter: [number, number] = home
    ? [home.lat, home.lon]
    : [36.44, 129.4];

  return (
    <div className="screen-pad">
      <h1 className="section-title">{t("settings_title")}</h1>

      {/* text size */}
      <section className="card">
        <h2 className="card-title">{t("set_text_size")}</h2>
        <div className="row" style={{ marginTop: 12 }}>
          <button
            type="button"
            className={`btn-pill${scale === 1 ? " selected" : ""}`}
            aria-pressed={scale === 1}
            onClick={() => setTextScale(1)}
          >
            {t("text_size_normal")}
          </button>
          <button
            type="button"
            className={`btn-pill${scale === 1.25 ? " selected" : ""}`}
            aria-pressed={scale === 1.25}
            onClick={() => setTextScale(1.25)}
            style={{ fontSize: "calc(var(--fs-body) * 1.25)" }}
          >
            {t("text_size_large")}
          </button>
        </div>
      </section>

      {/* language */}
      <section className="card">
        <h2 className="card-title">{t("set_language")}</h2>
        <div style={{ marginTop: 12 }}>
          <LangToggle />
        </div>
      </section>

      {/* home location */}
      <section className="card">
        <h2 className="card-title">{t("set_home")}</h2>
        <p className="card-body">
          {home
            ? `${t("home_current")}: ${home.lat.toFixed(5)}, ${home.lon.toFixed(5)}`
            : t("home_not_set")}
        </p>
        <div className="row wrap" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="btn-big-secondary"
            style={{ flex: 1 }}
            onClick={() => void useMyLocation()}
          >
            <IconLocation size={26} />
            {t("use_my_location")}
          </button>
          <button
            type="button"
            className="btn-big-secondary"
            style={{ flex: 1 }}
            onClick={() => setPicking(!picking)}
            aria-expanded={picking}
          >
            {t("pick_on_map")}
          </button>
        </div>
        {picking && (
          <div style={{ marginTop: 12 }}>
            <p className="card-body">{t("pick_on_map_hint")}</p>
            <div
              style={{
                height: 320,
                borderRadius: "var(--radius)",
                overflow: "hidden",
                border: "1px solid var(--hairline)",
              }}
            >
              <MapContainer
                center={mapCenter}
                zoom={12}
                style={{ height: "100%", width: "100%" }}
              >
                <TileLayer
                  url={config?.tile_url || OSM_TILES}
                  attribution={OSM_ATTR}
                />
                <PickHandler onPick={setPickPos} />
                {pickPos && (
                  <Marker position={[pickPos.lat, pickPos.lon]} icon={pickIcon} />
                )}
              </MapContainer>
            </div>
            <button
              type="button"
              className="btn-big-secondary"
              style={{ width: "100%", marginTop: 12 }}
              disabled={!pickPos}
              onClick={savePicked}
            >
              {t("save")}
            </button>
          </div>
        )}
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
      </section>

      {/* about + full disclaimer */}
      <section className="card">
        <h2 className="card-title">{t("about_title")}</h2>
        <p className="card-body">{t("about_body")}</p>
        <p className="card-body" style={{ color: "var(--ink-secondary)" }}>
          {t("mode_label")}:{" "}
          {config
            ? config.mode === "demo"
              ? t("mode_demo")
              : t("mode_live")
            : "—"}
          {" · "}
          {t("version_label")}: 0.1.0
        </p>
        <h2 className="card-title" style={{ marginTop: 16 }}>
          {t("disclaimer_title")}
        </h2>
        <p className="disclaimer">{t("disclaimer_body")}</p>
        {situation && (
          <p className="disclaimer" style={{ marginTop: 8 }}>
            {pick(situation, "disclaimer")}
          </p>
        )}
      </section>
    </div>
  );
}
