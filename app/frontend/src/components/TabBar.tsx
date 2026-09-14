import { useI18n } from "../i18n";
import {
  IconFamily,
  IconGuide,
  IconHome,
  IconMap,
  IconSettings,
} from "./Icons";

export type TabId = "home" | "map" | "guide" | "family" | "settings";

const TABS: { id: TabId; Icon: typeof IconHome }[] = [
  { id: "home", Icon: IconHome },
  { id: "map", Icon: IconMap },
  { id: "guide", Icon: IconGuide },
  { id: "family", Icon: IconFamily },
  { id: "settings", Icon: IconSettings },
];

/** Bottom tab bar: 5 tabs, large icons, labels ≥ 16 px. */
export function TabBar({
  active,
  onChange,
}: {
  active: TabId;
  onChange: (tab: TabId) => void;
}) {
  const { t } = useI18n();
  const labels: Record<TabId, string> = {
    home: t("tab_home"),
    map: t("tab_map"),
    guide: t("tab_guide"),
    family: t("tab_family"),
    settings: t("tab_settings"),
  };
  return (
    <nav className="tabbar" aria-label={t("app_name")}>
      {TABS.map(({ id, Icon }) => (
        <button
          key={id}
          type="button"
          className={`tab${active === id ? " active" : ""}`}
          aria-current={active === id ? "page" : undefined}
          onClick={() => onChange(id)}
        >
          <Icon size={34} />
          <span>{labels[id]}</span>
          <span className="tab-underline" />
        </button>
      ))}
    </nav>
  );
}
