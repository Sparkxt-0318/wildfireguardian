/**
 * "현장 전달 문구 / Field messages" dialog and the printable card, rendered in a local jsdom
 * (the vitest config runs in node; React and the TSX components are loaded at runtime, as in
 * features.plansheet.test.ts). All data is SYNTHETIC (lastmile.fixture.ts), except one live-session
 * test built over a real booth cache with SYNTHETIC live provenance (lastmile.cachedata.ts).
 */
import { createRequire } from 'node:module';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import type { HostInfo } from '../../planner/src/domain/types';
import { buildLastMileInputs } from '../../planner/src/features/lastmile/input';
import { buildFieldMessages, type FieldMessages } from '../../planner/src/features/lastmile/messages';
import type { ExplanationState } from '../../planner/src/features/lastmile/explanation';
import { liveOnlyArgs, liveOnlySession, loadBoothCacheModel } from './lastmile.cachedata';
import { synExplanation, synInput, synNoRoute, synUnresolved } from './lastmile.fixture';

const req = createRequire(new URL('../../planner/package.json', import.meta.url));
const { JSDOM } = req('jsdom') as { JSDOM: new (html?: string, opts?: Record<string, unknown>) => { window: Window & typeof globalThis } };

function installDom() {
  const dom = new JSDOM('<!doctype html><html lang="ko"><head></head><body></body></html>', { url: 'http://127.0.0.1/', pretendToBeVisual: true });
  const w = dom.window as unknown as Record<string, unknown>;
  const g = globalThis as unknown as Record<string, unknown>;
  for (const k of ['window', 'document', 'navigator', 'HTMLElement', 'HTMLDivElement', 'Element', 'Node', 'Text', 'SVGElement', 'Event', 'KeyboardEvent', 'MouseEvent', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame', 'DOMParser']) {
    Object.defineProperty(g, k, { value: k === 'window' ? dom.window : w[k], configurable: true, writable: true });
  }
  return dom;
}

interface ReactLike {
  createElement: (type: unknown, props: Record<string, unknown>) => unknown;
  act: (fn: () => unknown) => Promise<void> | void;
}
interface RootLike {
  render: (el: unknown) => void;
  unmount: () => void;
}

let React: ReactLike;
let createRoot: (el: Element) => RootLike;
let renderToStaticMarkup: (el: unknown) => string;
let Dialog: unknown;
let FieldCard: unknown;
let root: RootLike | null = null;
let host: HTMLDivElement | null = null;

beforeAll(async () => {
  installDom();
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  React = req('react') as ReactLike;
  createRoot = (req('react-dom/client') as { createRoot: (el: Element) => RootLike }).createRoot;
  renderToStaticMarkup = (req('react-dom/server') as { renderToStaticMarkup: (el: unknown) => string }).renderToStaticMarkup;
  const dialogPath = '../../planner/src/features/lastmile/FieldMessagesDialog';
  const cardPath = '../../planner/src/features/lastmile/FieldCard';
  Dialog = ((await import(/* @vite-ignore */ dialogPath)) as { FieldMessagesDialog: unknown }).FieldMessagesDialog;
  FieldCard = ((await import(/* @vite-ignore */ cardPath)) as { FieldCard: unknown }).FieldCard;
});

afterEach(async () => {
  if (root) await React.act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
  document.body.innerHTML = '';
  document.documentElement.className = '';
  vi.restoreAllMocks();
});

const ITEMS = (): FieldMessages[] => [buildFieldMessages(synInput(), synExplanation()), buildFieldMessages(synNoRoute(), synExplanation()), buildFieldMessages(synUnresolved())].map((fm, i) => ({ ...fm, urgencyRank: i + 1 }));

async function render(items: FieldMessages[], explanation: ExplanationState = { state: 'absent', url: '/data/explanations/x.json' }, lang: 'ko' | 'en' = 'ko', initialOriginId: string | null = null) {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  await React.act(async () => {
    root!.render(React.createElement(Dialog, { open: true, onClose: () => undefined, lang, items, initialOriginId, explanation }));
  });
  return document.querySelector('[data-testid="field-messages-dialog"]') as HTMLElement;
}

async function click(el: Element | null) {
  expect(el).not.toBeNull();
  await React.act(async () => {
    (el as HTMLElement).dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
}

describe('FieldMessagesDialog (jsdom)', () => {
  it('shows every text of the chosen origin in Korean and English with counters and the rule-check result', async () => {
    const dlg = await render(ITEMS(), { state: 'ready', url: 'x', file: synExplanation() }, 'ko', 'syn:origin:checked');
    expect(dlg.textContent).toContain('현장 전달 문구');
    expect(dlg.querySelectorAll('option').length).toBe(3);
    for (const block of ['sms', 'lms', 'broadcast', 'call']) {
      const b = dlg.querySelector(`[data-block="${block}"]`)!;
      expect(b.querySelectorAll('.wfgl-text').length).toBe(2);
      expect(b.querySelectorAll('pre').length).toBe(2);
    }
    expect(dlg.querySelector('[data-block="sms"] [data-lang="ko"] .wfgl-text__count')!.textContent).toBe('78 / 90바이트 (EUC-KR)');
    expect(dlg.querySelector('[data-block="sms"] [data-lang="en"] .wfgl-text__count')!.textContent).toBe('129 / 160자 (GSM-7)');
    // both languages are still awaiting native-speaker and field review, and say so
    expect(dlg.querySelectorAll('[data-block="sms"] [data-review="pending"]').length).toBe(2);
    expect(dlg.querySelector('[data-block="sms"] [data-review="pending"]')!.textContent).toBe('원어민·현장 검토 전');
    expect(dlg.querySelector('[data-testid="field-messages-checks"]')!.textContent).toBe('검사 통과: 길이·필수 문구·금지어');
    expect(dlg.querySelector('[data-explanation-state="ready"]')!.textContent).toContain('이 출발지: 이유 문장 포함');
    expect(dlg.querySelector('.wfgl-preview [data-card-status="checked_route"]')).not.toBeNull();
    expect(dlg.textContent).toContain('사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.');
    // the origin's own result source (per origin, never the session's)
    const src = dlg.querySelector('[data-testid="field-messages-source"]')!;
    expect(src.getAttribute('data-source')).toBe('cache');
    expect(src.textContent).toBe('결과 출처: 사전 계산 캐시 · synthetic_region/20250324T090000Z.json · 2026-10-18 07:54 KST');
  });

  it('a live result on a non-evaluated host: the panel and the CSV file name say so', async () => {
    const created: Blob[] = [];
    Object.defineProperty(URL, 'createObjectURL', { value: (b: Blob) => (created.push(b), 'blob:x'), configurable: true });
    Object.defineProperty(URL, 'revokeObjectURL', { value: () => undefined, configurable: true });
    vi.spyOn((window as unknown as { HTMLAnchorElement: { prototype: HTMLAnchorElement } }).HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const live = synInput({ testData: true, provenance: { source: 'live', computed: true, cachePath: null, cacheCreatedAtIso: null, host: { ko: 'Linux x86_64 · 4 vCPU', en: 'Linux x86_64 · 4 vCPU' } } });
    // the first origin is a cached one: the file name follows ANY origin's provenance, not the first's
    const items = [buildFieldMessages(synNoRoute()), buildFieldMessages(live)].map((fm, i) => ({ ...fm, urgencyRank: i + 1 }));
    const dlg = await render(items, undefined, 'ko', 'syn:origin:checked');
    const src = dlg.querySelector('[data-testid="field-messages-source"]')!;
    expect(src.getAttribute('data-source')).toBe('live');
    expect(src.getAttribute('data-computed')).toBe('true');
    expect(src.getAttribute('data-test-data')).toBe('true');
    expect(src.textContent).toBe('결과 출처: API 점검 결과 · 계산 호스트 Linux x86_64 · 4 vCPU · 평가 호스트 아님');
    await click(dlg.querySelector('[data-testid="field-messages-csv"]'));
    expect(dlg.textContent).toContain('저장됨: wfg_synthetic_region_20250324T090000Z_field_messages_TEST.csv');
  });

  it('a live session (real booth cache, SYNTHETIC live provenance): an origin without an API result is never called computed — panel, long text, card and exported CSV', async () => {
    const created: Blob[] = [];
    Object.defineProperty(URL, 'createObjectURL', { value: (b: Blob) => (created.push(b), 'blob:x'), configurable: true });
    Object.defineProperty(URL, 'revokeObjectURL', { value: () => undefined, configurable: true });
    vi.spyOn((window as unknown as { HTMLAnchorElement: { prototype: HTMLAnchorElement } }).HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const LINUX: HostInfo = { recorded: false, machine: 'x86_64', os: 'Linux', platform: 'Linux-6.18-x86_64-with-glibc2.39', cpuCount: 4 };
    const data = loadBoothCacheModel('uiseong_andong_2025/20250325T170000Z.json');
    // 용봉리 not computed yet, 구계리 refused, 광연리 every check failed before a job; 고곡리 not checkable
    const none = { notComputed: ['osm:node/415160449'], rejected: ['osm:node/415160471'], failed: ['osm:node/415160467'] };
    const targets = [...none.notComputed, ...none.rejected, ...none.failed, 'osm:node/415160364'];
    const items = buildLastMileInputs(liveOnlyArgs(data, liveOnlySession(data, LINUX, 'render', none))).map((i) => buildFieldMessages(i, null));
    for (const [lang, want, label] of [
      ['ko', 'API 점검 · 이 출발지 결과 없음', '결과 출처'],
      ['en', 'API checks · no result for this origin', 'Result source'],
    ] as const) {
      for (const id of targets) {
        const dlg = await render(items, undefined, lang, id);
        expect((dlg.querySelector('[data-testid="field-messages-origin"]') as HTMLSelectElement).value).toBe(id);
        const src = dlg.querySelector('[data-testid="field-messages-source"]')!;
        expect(src.getAttribute('data-source'), id).toBe('live');
        expect(src.getAttribute('data-computed'), id).toBe('false');
        expect(src.getAttribute('data-test-data'), id).toBe('false');
        expect(src.textContent, id).toBe(`${label}: ${want}`);
        // the long texts' data lines and the previewed card's staff line, as rendered
        expect(dlg.querySelector('[data-block="lms"] [data-lang="ko"] pre')!.textContent!.split('\n')[2], id).toBe('자료 기준: 2025년 3월 26일 02:00 (한국 시각) · API 점검 · 이 출발지 결과 없음');
        expect(dlg.querySelector('[data-block="lms"] [data-lang="en"] pre')!.textContent!.split('\n')[2], id).toBe('Data time: 2025-03-26 02:00 KST · API checks · no result for this origin');
        const card = dlg.querySelector('.wfgl-preview')!.textContent!;
        expect(card, id).toContain(want);
        expect(dlg.textContent, id).not.toMatch(/API 점검 결과|API results|계산 호스트|host unknown|실시간 API|Live API|평가 호스트 아님|not the evaluation host/);
        await React.act(() => root!.unmount());
        root = null;
        host?.remove();
      }
    }
    // the exported CSV (Korean headers): the same result source in the origin's row
    const dlg = await render(items, undefined, 'ko', targets[0]!);
    await click(dlg.querySelector('[data-testid="field-messages-csv"]'));
    expect(created.length).toBe(1);
    const csv = await created[0]!.text();
    const rows = csv.replace(/^﻿/, '').split('\r\n');
    const head = rows[0]!.split(',');
    const at = head.indexOf('결과 출처');
    expect(at).toBeGreaterThan(0);
    for (const id of targets) {
      const row = rows.find((r) => r.split(',')[1] === id)!;
      // the cells up to "결과 출처" hold no quotes or commas (ids, names, labels, times)
      expect(row.split(',')[at], id).toBe('API 점검 · 이 출발지 결과 없음');
    }
  }, 60_000);

  it('switching to an unresolved origin shows no departure time and a grey (never green) status', async () => {
    const dlg = await render(ITEMS());
    const select = dlg.querySelector('[data-testid="field-messages-origin"]') as HTMLSelectElement;
    await React.act(async () => {
      select.value = 'syn:origin:unresolved';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    expect(dlg.querySelector('.wfgl-dialog__status')!.getAttribute('data-kind')).toBe('unresolved');
    expect(dlg.querySelector('.wfgl-preview [data-card-status="unresolved"]')).not.toBeNull();
    expect(dlg.querySelector('.wfgl-preview .wfgl-card__big')).toBeNull();
    expect(dlg.querySelector('[data-explanation-state="absent"]')!.textContent).toContain('없음 — 이유 문장 없이 만듦');
  });

  it('copies a text to the clipboard', async () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const dlg = await render(ITEMS(), undefined, 'en', 'syn:origin:noroute');
    await click(dlg.querySelector('[data-testid="copy-sms-ko"]'));
    expect(writeText).toHaveBeenCalledWith(ITEMS()[1]!.text.ko.sms);
    expect(dlg.textContent).toContain('Copied');
  });

  it('prints only the cards: one card at A5 or A4, or every origin', async () => {
    const print = vi.fn();
    Object.defineProperty(window, 'print', { value: print, configurable: true });
    vi.useFakeTimers();
    try {
      const dlg = await render(ITEMS(), undefined, 'ko', 'syn:origin:checked');
      await click(dlg.querySelector('[data-testid="print-card-a4"]'));
      let rootEl = document.querySelector('[data-testid="field-card-print-root"]')!;
      expect(rootEl.getAttribute('data-print-size')).toBe('a4');
      expect(rootEl.querySelector('style')!.textContent).toContain('@page { size: A4 portrait');
      expect(rootEl.querySelectorAll('.wfgl-card').length).toBe(1);
      expect(document.documentElement.classList.contains('wfgl-printing-cards')).toBe(true);
      await React.act(async () => {
        vi.advanceTimersByTime(100);
        await Promise.resolve();
      });
      expect(print).toHaveBeenCalledTimes(1);
      await React.act(async () => {
        window.dispatchEvent(new Event('afterprint'));
      });
      expect(document.querySelector('[data-testid="field-card-print-root"]')).toBeNull();
      await click(dlg.querySelector('[data-testid="print-card-all"]'));
      rootEl = document.querySelector('[data-testid="field-card-print-root"]')!;
      expect(rootEl.getAttribute('data-print-size')).toBe('a5');
      expect(rootEl.querySelectorAll('.wfgl-card').length).toBe(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it('exports the CSV of every origin', async () => {
    const created: Blob[] = [];
    Object.defineProperty(URL, 'createObjectURL', { value: (b: Blob) => (created.push(b), 'blob:x'), configurable: true });
    Object.defineProperty(URL, 'revokeObjectURL', { value: () => undefined, configurable: true });
    const anchorClick = vi.spyOn((window as unknown as { HTMLAnchorElement: { prototype: HTMLAnchorElement } }).HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const dlg = await render(ITEMS());
    await click(dlg.querySelector('[data-testid="field-messages-csv"]'));
    expect(created.length).toBe(1);
    expect(anchorClick).toHaveBeenCalledTimes(1);
    expect(dlg.textContent).toContain('저장됨: wfg_synthetic_region_20250324T090000Z_field_messages.csv');
  });

  it('fails closed per output: only the text that fails is greyed and cannot be copied; the rest stays usable', async () => {
    const items = ITEMS();
    items[0] = { ...items[0]!, violations: ['ko.sms: 91 bytes > 90'] };
    const dlg = await render(items, undefined, 'ko', 'syn:origin:checked');
    expect(dlg.querySelector('[data-testid="field-messages-checks"]')!.textContent).toContain('검사 실패 — 회색으로 표시된 문구는 쓰지 마십시오: ko.sms: 91 bytes > 90');
    const disabled = (id: string) => (dlg.querySelector(`[data-testid="${id}"]`) as HTMLButtonElement).disabled;
    expect(disabled('copy-sms-ko')).toBe(true);
    expect(dlg.querySelector('[data-block="sms"] [data-lang="ko"] pre')!.getAttribute('data-failed')).toBe('true');
    for (const id of ['copy-sms-en', 'copy-lms-ko', 'copy-broadcast-ko', 'copy-call-ko', 'print-card-a5', 'print-card-a4', 'print-card-all']) expect(disabled(id), id).toBe(false);
    expect(dlg.querySelector('[data-block="lms"] [data-lang="ko"] pre')!.getAttribute('data-failed')).toBeNull();
  });

  it('a card that fails: no print of that card; "print all" prints the cards that pass and lists the one left out', async () => {
    const print = vi.fn();
    Object.defineProperty(window, 'print', { value: print, configurable: true });
    const items = ITEMS();
    items[1] = { ...items[1]!, violations: ['ko.card: missing "공식 대피 명령이 우선합니다."'] };
    vi.useFakeTimers();
    try {
      const dlg = await render(items, undefined, 'ko', 'syn:origin:noroute');
      const disabled = (id: string) => (dlg.querySelector(`[data-testid="${id}"]`) as HTMLButtonElement).disabled;
      expect(disabled('print-card-a5')).toBe(true);
      expect(disabled('print-card-a4')).toBe(true);
      expect(disabled('copy-sms-ko')).toBe(false);
      expect(dlg.querySelector('[data-testid="print-card-all-left-out"]')!.textContent).toBe('검사 실패로 인쇄하지 않는 카드 1곳: 2. 합성마을');
      await click(dlg.querySelector('[data-testid="print-card-all"]'));
      const rootEl = document.querySelector('[data-testid="field-card-print-root"]')!;
      expect([...rootEl.querySelectorAll('.wfgl-card')].map((c) => c.getAttribute('data-card-origin'))).toEqual(['syn:origin:checked', 'syn:origin:unresolved']);
      // the English card of the same origin passes and can be printed
      await click([...dlg.querySelectorAll('.wfgl-seg button')].find((b) => b.textContent === 'English')!);
      expect(disabled('print-card-a5')).toBe(false);
      expect(dlg.querySelector('[data-testid="print-card-all-left-out"]')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('a violation that names no output blocks every output of the origin', async () => {
    const items = ITEMS();
    items[0] = { ...items[0]!, violations: ['inconsistent plan'] };
    const dlg = await render(items, undefined, 'ko', 'syn:origin:checked');
    for (const id of ['copy-sms-ko', 'copy-sms-en', 'copy-lms-en', 'copy-call-ko', 'print-card-a5', 'print-card-a4']) expect((dlg.querySelector(`[data-testid="${id}"]`) as HTMLButtonElement).disabled, id).toBe(true);
    expect(dlg.querySelector('[data-testid="print-card-all-left-out"]')!.textContent).toContain('1. 합성마을');
  });
});

describe('FieldCard (static markup)', () => {
  it('leave_by: green check + text, the leave-by time in large type, official line, data time, model line', () => {
    const fm = buildFieldMessages(synInput());
    const html = renderToStaticMarkup(React.createElement(FieldCard, { card: fm.text.ko.card, size: 'a5', originId: fm.originId }));
    expect(html).toContain('data-card-status="checked_route"');
    expect(html).toContain('data-verdict-icon="checked_route"');
    expect(html).toContain('data-leave-by="18:30"');
    expect(html).toContain('공식 대피 명령이 우선합니다.');
    expect(html).toContain('자료 기준: 2025년 3월 24일 18:00 (한국 시각)');
    expect(html).toContain('모델 기반 계획 정보 · 실시간 아님');
    expect(html).toContain('wfgl-card--a5');
  });

  it('model_no_route: black slashed circle + text, no large time; unresolved: grey question mark', () => {
    const nr = buildFieldMessages(synNoRoute());
    const a = renderToStaticMarkup(React.createElement(FieldCard, { card: nr.text.en.card, size: 'a4', originId: nr.originId }));
    expect(a).toContain('data-verdict-icon="model_no_route"');
    expect(a).not.toContain('data-leave-by');
    expect(a).toContain('No checked vehicle route in the model');
    const un = buildFieldMessages(synUnresolved());
    const b = renderToStaticMarkup(React.createElement(FieldCard, { card: un.text.ko.card, size: 'a5', originId: un.originId }));
    expect(b).toContain('data-verdict-icon="unresolved"');
    expect(b).not.toContain('#1A9E55');
  });
});
