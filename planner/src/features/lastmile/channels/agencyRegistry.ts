/**
 * Registry of official issuing bodies (W-KIT W6; orchestrator decision after Mira's FAIL of the name-form guard).
 *
 * A contact line ("문의: <기관> <번호>") is rendered ONLY when the supplied agency name exactly matches an entry here,
 * after Unicode NFC normalisation and trimming of surrounding whitespace; nothing else widens the match. Anything else
 * renders no contact line and is reported to staff as "not in registry". The name-form check (`agencyLike`) is a lint
 * that every entry must pass (build-time test); it never admits a name.
 *
 * KEYED ON THE ISSUING LOCAL GOVERNMENT (시·군), per the orchestrator: under current law (재난안전법 제40조①) only the
 * 시장·군수·구청장 and the 지역통제단장 may order an evacuation, and the 2025 orders were tagged with the county name
 * (예규 361 제10조②: the sending body's name is mandatory). Not registered: 읍·면 offices (the draft 시행령 제49조⑥ is
 * not in force), departments (only a secondary provincial table names them so far), 경상북도 / 산림청 / 행정안전부 (not
 * evacuation-order issuers under 제40조①).
 *
 * INCOMPLETE. 영덕군 is not registered: no verbatim sender tag and no own-site source yet (its site was unreachable). To
 * add a body: the exact official name as the body writes it, its own published English name only (never a romanisation
 * made here), a source URL for each, and the reviewer. Contact NUMBERS are never stored here: they are supplied inputs,
 * checked for a Korean phone-number shape and labelled to staff as supplied and unverified.
 */
export interface RegistryEntry {
  /** exact official Korean name of the issuing 시·군 */
  ko: string;
  /** the body's own published English name, or null (no English contact field then) */
  en: string | null;
  /** where the exact names come from */
  source: string;
}

export const AGENCY_REGISTRY: readonly RegistryEntry[] = [
  { ko: '의성군', en: null, source: '긴급재난문자 sender tag "[의성군]", 2025-03-25 16:14 (https://newstapa.org/article/Z7eDJ; via Sofia). English: own site unreachable — none.' },
  { ko: '청송군', en: null, source: '긴급재난문자, 2025-03-25 16:49 (heraldcorp 10449892; via Sofia). English: none found.' },
  { ko: '안동시', en: 'Andong City', source: '긴급재난문자, 2025-03-25 (newsis NISX20250328_0003118155; via Sofia). English: own English site https://www.andong.go.kr/en/main.do ("Andong City").' },
  { ko: '영양군', en: null, source: '긴급재난문자, 2025-03-25 18:18 (imaeil 2025032518271151259; via Sofia). English: own site unreachable — none.' },
];

let override: readonly RegistryEntry[] | null = null;

/** The registry in force. App code always gets the committed one. */
export function activeRegistry(): readonly RegistryEntry[] {
  return override ?? AGENCY_REGISTRY;
}

/**
 * TEST ONLY: run `fn` with a synthetic registry. Not reachable from app code: a test asserts that nothing under
 * planner/src calls it. Every entry still needs a non-empty source.
 */
export function withTestRegistryOnly<T>(entries: readonly RegistryEntry[], fn: () => T): T {
  if (entries.some((e) => !e.source.trim())) throw new Error('registry entries need a source');
  const prev = override;
  override = entries;
  try {
    return fn();
  } finally {
    override = prev;
  }
}
