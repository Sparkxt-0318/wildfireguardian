/**
 * Registry of official issuing bodies (W-KIT W6; orchestrator decision after Mira's FAIL of the name-form guard).
 *
 * A contact line ("문의: <기관> <번호>") is rendered ONLY when the supplied agency name exactly matches an entry here.
 * Anything else renders no contact line and is reported to staff as "not in registry". The name-form check
 * (`agencyLike`) is a secondary lint only.
 *
 * INCOMPLETE. It holds only bodies whose exact name has a source. To add one: the exact official Korean name as the body
 * itself writes it, its official English name only if the body publishes one (never a romanisation made here), a
 * source URL for each, and the reviewer. Contact numbers are NEVER stored here: they are supplied inputs.
 */
export interface RegistryEntry {
  /** exact official Korean name */
  ko: string;
  /** the body's own published English name, or null (no English contact field then) */
  en: string | null;
  /** where the exact name comes from */
  source: string;
}

export const AGENCY_REGISTRY: readonly RegistryEntry[] = [
  { ko: '의성군', en: null, source: '긴급재난문자 sender tag "[의성군]", 2025-03-25 16:14 (newstapa Z7eDJ; via Sofia)' },
  { ko: '청송군', en: null, source: '긴급재난문자, 2025-03-25 16:49 (heraldcorp 10449892; via Sofia)' },
  { ko: '안동시', en: null, source: '긴급재난문자, 2025-03-25 (newsis NISX20250328_0003118155; via Sofia)' },
  { ko: '영양군', en: null, source: '긴급재난문자, 2025-03-25 18:18 (imaeil 2025032518271151259; via Sofia)' },
  { ko: '산림청', en: null, source: '산림재난방지법 제33조 (law.go.kr; via Sofia)' },
  { ko: '행정안전부', en: null, source: '행정안전부공고 제2026-1391호, 2026-11-04 (opinion.lawmaking.go.kr/gcom/ogLmPp/89332; via Sofia)' },
];
