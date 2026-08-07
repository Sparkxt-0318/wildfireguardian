import { useCallback, useEffect, useState } from "react";
import {
  getConfig,
  subscribeSituation,
  type AppConfig,
  type Situation,
} from "./api/client";
import { DemoBanner } from "./components/DemoBanner";
import { LangToggle } from "./components/LangToggle";
import { TabBar, type TabId } from "./components/TabBar";
import { useI18n } from "./i18n";
import { DEFAULT_COORDS, type Coords } from "./lib/geo";
import {
  applyTextScale,
  getPref,
  setPref,
  type HomeLocation,
} from "./lib/prefs";
import { stop as stopTts } from "./lib/tts";
import { FamilyScreen } from "./screens/FamilyScreen";
import { GuideScreen } from "./screens/GuideScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { MapScreen } from "./screens/MapScreen";
import { SettingsScreen } from "./screens/SettingsScreen";

export default function App() {
  const { pair } = useI18n();
  const [tab, setTab] = useState<TabId>("home");
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [home, setHome] = useState<HomeLocation | null>(() => getPref("home"));
  const [coords, setCoords] = useState<Coords>(() => {
    const saved = getPref("home");
    return saved ? { lat: saved.lat, lon: saved.lon } : DEFAULT_COORDS;
  });
  const [situation, setSituation] = useState<Situation | null>(null);
  const [streamFailed, setStreamFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [routeRequested, setRouteRequested] = useState(false);

  // apply persisted text size once
  useEffect(() => {
    applyTextScale(getPref("textScale") ?? 1);
  }, []);

  // config (mode/banner/tiles) — non-fatal when unreachable
  useEffect(() => {
    let alive = true;
    getConfig()
      .then((c) => alive && setConfig(c))
      .catch(() => alive && setConfig(null));
    return () => {
      alive = false;
    };
  }, [retryKey]);

  // live situation: SSE with 10 s polling fallback (api/client.ts)
  useEffect(() => {
    setStreamFailed(false);
    const handle = subscribeSituation(
      coords.lat,
      coords.lon,
      (s) => {
        setSituation(s);
        setStreamFailed(false);
      },
      () => setStreamFailed(true),
    );
    return () => handle.close();
  }, [coords.lat, coords.lon, retryKey]);

  // stop speech whenever the user navigates (spec: stop-on-navigate)
  const changeTab = useCallback((next: TabId) => {
    stopTts();
    if (next !== "map") setRouteRequested(false);
    setTab(next);
  }, []);

  const openMap = useCallback(() => {
    stopTts();
    setRouteRequested(false);
    setTab("map");
  }, []);

  const openRoute = useCallback(() => {
    stopTts();
    setRouteRequested(true);
    setTab("map");
  }, []);

  const onHomeChange = useCallback((next: HomeLocation) => {
    setHome(next);
    setPref("home", next);
    setCoords({ lat: next.lat, lon: next.lon });
  }, []);

  const onCoordsChange = useCallback((next: Coords) => {
    setCoords(next);
  }, []);

  // ---- calm, huge-type, bilingual loading / error states -------------------
  const [loadTitleA, loadTitleB] = pair("loading_title");
  const [loadSubA, loadSubB] = pair("loading_sub");
  const [errTitleA, errTitleB] = pair("error_title");
  const [errSubA, errSubB] = pair("error_sub");
  const [retryA, retryB] = pair("error_retry");

  const needsSituation = tab === "home" || tab === "guide";

  let screenEl;
  if (needsSituation && !situation) {
    screenEl = streamFailed ? (
      <div className="big-state screen-pad" role="alert">
        <p className="big-state-word">{errTitleA}</p>
        <p className="big-state-sub">{errTitleB}</p>
        <p className="big-state-sub">
          {errSubA} · {errSubB}
        </p>
        <button
          type="button"
          className="btn-big-secondary"
          style={{ margin: "0 auto" }}
          onClick={() => setRetryKey((k) => k + 1)}
        >
          {retryA} / {retryB}
        </button>
      </div>
    ) : (
      <div className="big-state screen-pad" role="status">
        <p className="big-state-word">{loadTitleA}</p>
        <p className="big-state-sub">{loadTitleB}</p>
        <p className="big-state-sub">
          {loadSubA} · {loadSubB}
        </p>
      </div>
    );
  } else if (tab === "home" && situation) {
    screenEl = (
      <HomeScreen
        situation={situation}
        onOpenMap={openMap}
        onOpenRoute={openRoute}
      />
    );
  } else if (tab === "guide" && situation) {
    screenEl = (
      <GuideScreen
        situation={situation}
        onOpenMap={openMap}
        onOpenRoute={openRoute}
      />
    );
  } else if (tab === "map") {
    screenEl = (
      <MapScreen
        coords={coords}
        onCoordsChange={onCoordsChange}
        situation={situation}
        config={config}
        routeRequested={routeRequested}
      />
    );
  } else if (tab === "family") {
    screenEl = <FamilyScreen />;
  } else {
    screenEl = (
      <SettingsScreen
        config={config}
        situation={situation}
        home={home}
        onHomeChange={onHomeChange}
      />
    );
  }

  return (
    <div className="app-shell">
      <DemoBanner config={config} />
      {tab !== "map" && (
        <div className="top-bar">
          <p className="app-name">{pair("app_name")[0]}</p>
          <LangToggle />
        </div>
      )}
      <main className="screen">{screenEl}</main>
      <TabBar active={tab} onChange={changeTab} />
    </div>
  );
}
