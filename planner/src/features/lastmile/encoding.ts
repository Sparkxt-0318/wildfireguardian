/**
 * Length rules of the last-mile outputs (pure, no DOM). Unit-tested in tests/planner/lastmile.test.ts.
 *
 * - Korean SMS / LMS: bytes in strict EUC-KR (KS X 1001): ASCII = 1 byte, a KS X 1001 character
 *   = 2 bytes. Characters outside KS X 1001 (e.g. "—", rare Hangul syllables, emoji) are reported
 *   as unencodable: a carrier may show them as "?" or switch encodings, so the templates never use
 *   them and the tests fail if data puts one in.
 * - English SMS: GSM 03.38 7-bit default alphabet; basic characters count 1 septet, the extension
 *   table (^{}\[~]|€ and form feed) 2. Anything else would force UCS-2 (70 characters) and is
 *   reported.
 * - Spoken length: Korean syllables (numbers expanded the way they are read aloud) and English
 *   words (each digit counted as a word — deliberately pessimistic).
 */

/** Korean single SMS (단문) limit, bytes. */
export const SMS_KO_MAX_BYTES = 90;
/** Korean LMS (장문) limit, bytes. */
export const LMS_MAX_BYTES = 2000;
/** English single SMS limit, GSM-7 characters. */
export const SMS_EN_MAX_GSM7 = 160;
/** Village broadcast limit, seconds when read aloud. */
export const BROADCAST_MAX_S = 60;
/**
 * Assumed Korean reading rate for a loudspeaker announcement to older listeners: 3.0 syllables
 * per second, pauses included. Hwang & Lee (2012, J. Acoust. Soc. Korea 31(2):63–72) measured
 * 5.04 syllables/s overall (pauses included) for native Korean speakers reading a passage aloud;
 * 3.0 is about 40 % slower, so a script that fits at 3.0 also fits a slow, deliberate reader.
 */
export const KO_SYLLABLES_PER_S = 3.0;
/**
 * Assumed English reading rate: 2.0 words per second (120 words per minute) — an assumption without
 * a measured source, chosen slow for loudspeaker listening; every digit is counted as a word.
 */
export const EN_WORDS_PER_S = 2.0;

let KS_TABLE: Set<string> | null = null;
let KS_VERIFIED = false;

/**
 * The KS X 1001 repertoire, built once from the platform's WHATWG "euc-kr" decoder (lead and
 * trail bytes 0xA1–0xFE only, i.e. the KS X 1001 plane, without the private-use rows the decoder
 * maps for the user-defined area).
 */
function ksTable(): Set<string> {
  if (KS_TABLE) return KS_TABLE;
  const set = new Set<string>();
  try {
    const dec = new TextDecoder('euc-kr', { fatal: true });
    const buf = new Uint8Array(2);
    for (let a = 0xa1; a <= 0xfe; a += 1) {
      for (let b = 0xa1; b <= 0xfe; b += 1) {
        buf[0] = a;
        buf[1] = b;
        let s: string;
        try {
          s = dec.decode(buf);
        } catch {
          continue;
        }
        if (s.length !== 1) continue;
        const cp = s.charCodeAt(0);
        if (cp >= 0xe000 && cp <= 0xf8ff) continue; // user-defined rows → private use area
        set.add(s);
      }
    }
    KS_VERIFIED = set.size > 8000;
  } catch {
    KS_VERIFIED = false;
  }
  KS_TABLE = set;
  return set;
}

export interface ByteCount {
  bytes: number;
  /** characters that strict EUC-KR (KS X 1001) cannot encode (counted as 2 bytes) */
  unencodable: string[];
  /** false when the platform has no EUC-KR decoder (the count is then an estimate) */
  verified: boolean;
}

/** Byte length in strict EUC-KR (KS X 1001). */
export function eucKrBytes(text: string): ByteCount {
  const ks = ksTable();
  let bytes = 0;
  const bad: string[] = [];
  for (const ch of text) {
    const cp = ch.codePointAt(0)!;
    if (cp < 0x80) bytes += 1;
    else {
      bytes += 2;
      if (KS_VERIFIED && !ks.has(ch)) bad.push(ch);
    }
  }
  return { bytes, unencodable: [...new Set(bad)], verified: KS_VERIFIED };
}

const GSM_BASIC =
  '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà';
const GSM_EXTENSION = '\f^{}\\[~]|€';

export interface Gsm7Count {
  /** septets (extension characters count 2) */
  chars: number;
  /** characters outside the GSM 03.38 default alphabet and its extension table */
  nonGsm: string[];
}

export function gsm7Length(text: string): Gsm7Count {
  let chars = 0;
  const bad: string[] = [];
  for (const ch of text) {
    if (GSM_BASIC.includes(ch)) chars += 1;
    else if (GSM_EXTENSION.includes(ch)) chars += 2;
    else {
      chars += 1;
      bad.push(ch);
    }
  }
  return { chars, nonGsm: [...new Set(bad)] };
}

// ---------------------------------------------------------------- spoken length

const SINO = ['영', '일', '이', '삼', '사', '오', '육', '칠', '팔', '구'];
const NATIVE_ONES = ['', '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉'];
const NATIVE_TENS = ['', '열', '스물', '서른', '마흔', '쉰', '예순', '일흔', '여든', '아흔'];

/** Sino-Korean reading of a non-negative integer ("2025" → "이천이십오"). */
export function sinoKorean(n: number): string {
  if (!Number.isFinite(n) || n < 0) return '';
  let v = Math.floor(n);
  if (v === 0) return '영';
  const units = ['', '십', '백', '천'];
  const big = ['', '만', '억', '조'];
  let out = '';
  let group = 0;
  while (v > 0 && group < big.length) {
    const g = v % 10000;
    if (g > 0) {
      const ds = String(g).padStart(4, '0');
      let gs = '';
      for (let i = 0; i < 4; i += 1) {
        const d = Number(ds[i]);
        const u = units[3 - i]!;
        if (d === 0) continue;
        gs += (d === 1 && u ? '' : SINO[d]) + u;
      }
      out = gs + big[group] + out;
    }
    v = Math.floor(v / 10000);
    group += 1;
  }
  return out;
}

/** Native Korean counting reading for 1–99 ("4" → "네" before a counter); other values Sino. */
export function nativeKorean(n: number): string {
  if (!Number.isInteger(n) || n < 1 || n > 99) return sinoKorean(n);
  if (n === 20) return '스무';
  return NATIVE_TENS[Math.floor(n / 10)]! + NATIVE_ONES[n % 10]!;
}

/** Counters read with native numbers ("네 가지", "세 곳", "한 시간"). */
const NATIVE_COUNTERS = ['가지', '곳', '개', '명', '시간', '대'];

/**
 * The text as it is read aloud: clock times, hours, counters and other numbers spelled out in
 * Hangul ("오후 6시 40분" → "오후 여섯시 사십분", "119" → "일일구"). Used only for the length estimate.
 */
export function koReadAloud(text: string): string {
  let s = text;
  // HH:MM → native hour + Sino minutes
  s = s.replace(/(\d{1,2}):(\d{2})/g, (_m, h: string, mi: string) => {
    const hh = Number(h);
    const mm = Number(mi);
    const hour = hh >= 1 && hh <= 12 ? nativeKorean(hh) : sinoKorean(hh);
    return `${hour}시${mm ? ` ${sinoKorean(mm)}분` : ''}`;
  });
  // N시 (hour of day; not "N시간")
  s = s.replace(/(\d{1,2})\s*시(?!간)/g, (_m, h: string) => {
    const hh = Number(h);
    return `${hh >= 1 && hh <= 12 ? nativeKorean(hh) : sinoKorean(hh)}시`;
  });
  // native counters
  s = s.replace(new RegExp(`(\\d{1,2})\\s*(${NATIVE_COUNTERS.join('|')})`, 'g'), (_m, n: string, c: string) => `${nativeKorean(Number(n))} ${c}`);
  // units read in full ("1.4 km" → "1.4 킬로미터", "650 m" → "650 미터")
  s = s.replace(/(\d)\s*km\b/g, '$1 킬로미터').replace(/(\d)\s*m\b/g, '$1 미터');
  // decimals: "1.4" → "일점사"
  s = s.replace(/(\d+)\.(\d+)/g, (_m, a: string, b: string) => `${sinoKorean(Number(a))}점${[...b].map((d) => SINO[Number(d)]).join('')}`);
  // emergency / phone style numbers: read digit by digit
  s = s.replace(/\b(1\d{2})\b(?!\s*(년|월|일|분|초|번|호|m|km))/g, (_m, n: string) => [...n].map((d) => SINO[Number(d)]).join(''));
  // any other number: Sino-Korean
  s = s.replace(/\d+/g, (n) => sinoKorean(Number(n)));
  return s;
}

/** Hangul syllables read aloud (Latin letters count one syllable each — pessimistic). */
export function koSpokenSyllables(text: string): number {
  const read = koReadAloud(text);
  let n = 0;
  for (const ch of read) {
    const cp = ch.codePointAt(0)!;
    if (cp >= 0xac00 && cp <= 0xd7a3) n += 1;
    else if (/[A-Za-z]/.test(ch)) n += 1;
  }
  return n;
}

/** Spoken English words; each digit counts as a word and "p.m." as two (pessimistic). */
export function enSpokenWords(text: string): number {
  let n = 0;
  for (const raw of text.split(/\s+/)) {
    const tok = raw.replace(/^[^\p{L}\p{N}]+/u, '').replace(/[^\p{L}\p{N}.]+$/u, '');
    if (!tok) continue;
    if (/^[ap]\.?m\.?$/i.test(tok)) {
      n += 2;
      continue;
    }
    const digits = tok.replace(/[^0-9]/g, '').length;
    // "1.4" is read "one point four"
    const points = (tok.match(/\d\.\d/g) ?? []).length;
    const letters = /\p{L}/u.test(tok) ? 1 : 0;
    n += digits + points + letters;
  }
  return n;
}

/** Estimated reading time (s) of a spoken script at the assumed rate. */
export function spokenSeconds(text: string, lang: 'ko' | 'en'): number {
  return lang === 'ko' ? koSpokenSyllables(text) / KO_SYLLABLES_PER_S : enSpokenWords(text) / EN_WORDS_PER_S;
}
