/**
 * Narrow screens (≤ 900 px, e.g. a 375 px phone): the three columns (list · map · details) become
 * one pane at a time, switched by this tab bar (src/styles/mobile.css). Selecting a village or
 * facility opens its details. Wide screens never show the bar and keep the three columns.
 */
import { useEffect, useRef } from 'react';
import { create } from 'zustand';
import { registerStrings, useT } from '../i18n';
import { useStore } from '../state/store';
import { useScenarioPlaces } from '../state/selectors';

registerStrings({
  ko: { 'mobile.nav': '화면 선택', 'mobile.list': '목록', 'mobile.map': '지도', 'mobile.detail': '상세' },
  en: { 'mobile.nav': 'Choose a view', 'mobile.list': 'List', 'mobile.map': 'Map', 'mobile.detail': 'Details' },
});

export type MobilePane = 'list' | 'map' | 'detail';

export const NARROW_QUERY = '(max-width: 900px)';

export const useMobilePane = create<{ pane: MobilePane; setPane: (p: MobilePane) => void }>((set) => ({
  pane: 'list',
  setPane: (pane) => set({ pane }),
}));

export function setMobilePane(pane: MobilePane): void {
  useMobilePane.getState().setPane(pane);
}

export function isNarrowScreen(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(NARROW_QUERY).matches;
}

export function MobileNav() {
  const t = useT();
  const pane = useMobilePane((s) => s.pane);
  const setPane = useMobilePane((s) => s.setPane);
  const selected = useStore((s) => s.selectedOriginId);
  const { origins } = useScenarioPlaces();
  // a newly selected village or facility opens its details (list row, map marker or deep link)
  const last = useRef<string | null>(null);
  useEffect(() => {
    if (selected && selected !== last.current && isNarrowScreen()) setPane('detail');
    last.current = selected;
  }, [selected, setPane]);
  const tabs: { id: MobilePane; label: string; extra?: string }[] = [
    { id: 'list', label: t('mobile.list'), extra: String(origins.length) },
    { id: 'map', label: t('mobile.map') },
    { id: 'detail', label: t('mobile.detail') },
  ];
  return (
    <nav className="mobile-nav" aria-label={t('mobile.nav')} data-testid="mobile-nav">
      {tabs.map((tab) => (
        <button key={tab.id} type="button" aria-pressed={pane === tab.id} onClick={() => setPane(tab.id)} data-testid={`mobile-tab-${tab.id}`}>
          {tab.label}
          {tab.extra ? <span className="mobile-nav-n tnum">{tab.extra}</span> : null}
        </button>
      ))}
    </nav>
  );
}
