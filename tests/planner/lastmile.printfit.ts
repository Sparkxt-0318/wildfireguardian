/**
 * Browser-free print-fit estimate of an origin card (FieldCard + lastmile.css): the card's boxes
 * filled with its text, wrapped greedily at spaces with the bundled font's measured advance widths.
 * Used by lastmile.print.test.ts, which also checks in Chromium that it never undershoots the real
 * layout, so it can stand in for the browser where Playwright is not installed.
 */
import type { CardContent } from '../../planner/src/features/lastmile/compose';

export type CardSize = 'a5' | 'a4';

const PT_PX = 96 / 72;
const MM_PX = 96 / 25.4;

/** Page box and body size of each card size (must match lastmile.css). */
export const BOX: Record<CardSize, { wMm: number; hMm: number; padXMm: number; padYMm: number; pt: number }> = {
  a5: { wMm: 148, hMm: 209.6, padXMm: 8, padYMm: 7, pt: 14 },
  a4: { wMm: 210, hMm: 296.6, padXMm: 16, padYMm: 14, pt: 18 },
};
const LH = 1.32;
const BORDER2PT = 2 * PT_PX;
const BORDER1_2PT = 1.2 * PT_PX;
/** letter-spacing of .wfgl-card (inherited as a length: -0.005 × the card's font size) and of the title (-0.02 em) */
const CARD_LS_EM = -0.005;
const TITLE_LS_EM = -0.02;

/**
 * Advance widths of the bundled Pretendard Variable, in thousandths of an em at weight 400 and at
 * weight 900, for printable ASCII (U+0020–U+007E) followed by '·', '–' and '—'. Measured once in
 * Chromium (one glyph at a time at 1000 px, kerning off) and rounded up; the widths at the weights
 * in between are linear in weight (checked at 600–850: within 0.0004 em), and 0.0005 em is added
 * per glyph. Every Hangul syllable is 0.8643 em at every weight; any other glyph counts as 1 em.
 * Kerning is ignored and lines break only at spaces, which can only overstate the height.
 */
const ADV_CHARS = [...Array.from({ length: 95 }, (_, i) => String.fromCharCode(0x20 + i)), '·', '–', '—'];
const ADV_400 = '251 257 379 600 608 863 610 202 341 341 471 627 258 433 254 334 596 439 587 618 625 597 614 552 607 614 254 254 627 627 627 480 880 646 620 694 686 568 557 709 707 245 516 622 534 853 718 727 605 727 609 608 612 708 646 916 613 634 595 341 334 341 443 425 469 536 591 530 591 553 337 580 563 218 218 517 218 834 557 568 580 580 350 497 340 553 530 778 513 530 513 341 306 341 627 254 471 958'.split(' ').map(Number);
const ADV_900 = '218 341 375 642 646 1025 674 195 423 423 584 672 307 460 301 397 704 490 627 654 680 648 664 592 668 664 301 301 672 672 672 578 871 767 648 745 712 603 567 749 729 281 569 691 555 904 705 771 636 772 647 646 665 702 767 1056 735 737 672 423 397 423 484 477 483 572 625 587 625 589 388 628 625 284 284 586 284 910 625 605 627 627 417 568 391 627 586 847 577 586 573 423 389 423 672 301 486 972'.split(' ').map(Number);
const ADV = new Map(ADV_CHARS.map((c, i) => [c, [ADV_400[i]! / 1000, ADV_900[i]! / 1000] as const]));

function glyphEm(ch: string, weight: number): number {
  const cp = ch.codePointAt(0)!;
  if (cp >= 0xac00 && cp <= 0xd7a3) return 0.865;
  const a = ADV.get(ch);
  return a ? a[0] + ((a[1] - a[0]) * (weight - 400)) / 500 + 0.0005 : 1;
}

/** A font: size (px), weight and letter-spacing (px). */
interface Font {
  fs: number;
  weight: number;
  ls: number;
}

const glyphPx = (ch: string, f: Font) => glyphEm(ch, f.weight) * f.fs + f.ls;
const runPx = (text: string, f: Font) => [...text].reduce((a, c) => a + glyphPx(c, f), 0);

/**
 * Lines of a paragraph wrapped greedily at its spaces (word-break: keep-all — no break inside a
 * word); a word longer than the line starts a line of its own and breaks between any two glyphs
 * (overflow-wrap: anywhere). `tailPx` is added to the last word (an inline box set right after it).
 */
function wrapLines(text: string, widthPx: number, f: Font, tailPx = 0): number {
  const words = text.split(' ');
  const space = glyphPx(' ', f);
  let lines = 1;
  let x = 0;
  words.forEach((word, i) => {
    const glyphs = [...word].map((c) => glyphPx(c, f));
    if (i === words.length - 1 && tailPx > 0) glyphs.push(tailPx);
    const w = glyphs.reduce((a, b) => a + b, 0);
    if (i > 0 && x + space + w <= widthPx) x += space + w;
    else if (w <= widthPx) {
      if (i > 0) lines += 1;
      x = w;
    } else {
      if (i > 0) lines += 1;
      x = 0;
      for (const g of glyphs) {
        if (x + g > widthPx && x > 0) {
          lines += 1;
          x = 0;
        }
        x += g;
      }
    }
  });
  return lines;
}

interface FlexItem {
  text: string;
  font: Font;
  /** line-height (multiple of the font size) */
  lh: number;
  /** horizontal and vertical padding + border (px) */
  padX?: number;
  padY?: number;
}

/**
 * Height of a wrapping flex row (flex-wrap: wrap): an item keeps its one-line width and moves to the
 * next line whole; an item wider than the row gets a line of its own and wraps its text inside.
 * `lineSlackPx` is added per line for baseline alignment of items of different sizes.
 */
function flexRowsHeight(items: FlexItem[], gapPx: number, widthPx: number, lineSlackPx: number): number {
  const rows: number[] = [];
  let x = -1;
  for (const it of items) {
    const one = runPx(it.text, it.font) + (it.padX ?? 0);
    const h1 = it.font.fs * it.lh + (it.padY ?? 0);
    if (one > widthPx) {
      rows.push(wrapLines(it.text, widthPx - (it.padX ?? 0), it.font) * it.font.fs * it.lh + (it.padY ?? 0));
      x = widthPx;
    } else if (x >= 0 && x + gapPx + one <= widthPx) {
      x += gapPx + one;
      rows[rows.length - 1] = Math.max(rows[rows.length - 1]!, h1);
    } else {
      rows.push(h1);
      x = one;
    }
  }
  return rows.reduce((a, h) => a + h + lineSlackPx, 0);
}

/** Estimated height (px) of each part of a card. */
export interface CardEstimate {
  usedPx: number;
  availablePx: number;
  parts: Record<'head' | 'title' | 'status' | 'big' | 'lines' | 'official' | 'data' | 'model' | 'limits' | 'foot' | 'gaps', number>;
}

/** Estimated content height (px) of a card next to the height its page box offers (sizes, weights and spacing from lastmile.css). */
export function estimate(card: CardContent, size: CardSize): CardEstimate {
  const b = BOX[size];
  const F = b.pt * PT_PX;
  const W = (b.wMm - 2 * b.padXMm) * MM_PX;
  const H = (b.hMm - 2 * b.padYMm) * MM_PX;
  const ls = CARD_LS_EM * F;
  const font = (scale: number, weight: number): Font => ({ fs: scale * F, weight, ls });
  const para = (text: string, f: Font, widthPx: number, lh = LH) => wrapLines(text, widthPx, f) * f.fs * lh;
  const parts: CardEstimate['parts'] = { head: 0, title: 0, status: 0, big: 0, lines: 0, official: 0, data: 0, model: 0, limits: 0, foot: 0, gaps: 0 };
  // head: a wrapping flex row at 0.72 em (A5: 12 pt) (document 800, the rest 600, badges 800 with
  // 0.3 em side padding and a 1.2 pt border), gap 0.35 em, padding-bottom 0.3 em, 1.2 pt rule
  const small = size === 'a5' ? (12 * PT_PX) / F : null;
  const hs = small ?? 0.72;
  const hf = hs * F;
  const headItems: FlexItem[] = [
    { text: card.docTitle, font: font(hs, 800), lh: LH },
    { text: '·', font: font(hs, 600), lh: LH },
    { text: card.regionName, font: font(hs, 600), lh: LH },
    { text: '·', font: font(hs, 600), lh: LH },
    { text: card.fireInputLabel, font: font(hs, 600), lh: LH },
    ...card.badges.map((x) => ({ text: x, font: font(hs, 800), lh: LH, padX: 0.6 * hf + 2 * BORDER1_2PT, padY: 2 * BORDER1_2PT })),
  ];
  parts.head = flexRowsHeight(headItems, 0.35 * hf, W, 0) + 0.3 * hf + BORDER1_2PT;
  // title (1.5 em, 800, line-height 1.15, letter-spacing -0.02 em, margin-top 0.2 em); the category
  // follows the last word at half size (A5: 12 pt) (700) after a 0.4 em margin, with no break before it
  const tf = 1.5 * F;
  const titleFont: Font = { fs: tf, weight: 800, ls: TITLE_LS_EM * tf };
  const cf = size === 'a5' ? 12 * PT_PX : 0.5 * tf;
  const catPx = card.category ? 0.4 * cf + runPx(card.category, { fs: cf, weight: 700, ls: TITLE_LS_EM * tf }) : 0;
  parts.title = 0.2 * tf + wrapLines(card.title, W, titleFont, catPx) * tf * 1.15;
  // status block (1.12 em, 800, line-height 1.25, padding 0.25/0.5 em, 2 pt border, 30 px icon, gap
  // 0.4 em, margin-top 0.35 em)
  const sf = 1.12 * F;
  parts.status = 0.35 * sf + Math.max(para(card.statusText, font(1.12, 800), W - sf - 2 * BORDER2PT - 30 - 0.4 * sf, 1.25), 30) + 0.5 * sf + 2 * BORDER2PT;
  // large leave-by time: a wrapping flex row (label 1.2 em 800, time 2.1 em 850 line-height 1.05,
  // sub-line 1 em 650), gap 0.4 em, margin-top 0.25 em; baseline alignment adds up to 0.05 em a line
  if (card.big) {
    const bigItems: FlexItem[] = [
      { text: card.big.label, font: font(1.2, 800), lh: LH },
      { text: card.big.time, font: font(2.1, 850), lh: 1.05 },
      { text: card.big.sub, font: font(1, 650), lh: LH },
    ];
    parts.big = 0.25 * F + flexRowsHeight(bigItems, 0.4 * F, W, 0.05 * F);
  }
  // message lines (bullet indent 0.85 em, gap 0.15 em, margin-top 0.35 em; instruction 760, reason 620)
  const weightOf = (role: string) => (role === 'instruction' ? 760 : role === 'reason' ? 620 : 400);
  parts.lines = 0.35 * F + card.lines.reduce((a, l) => a + para(l.text, font(1, weightOf(l.role)), W - 0.85 * F), 0) + Math.max(0, card.lines.length - 1) * 0.15 * F;
  // bottom block (padding-top 0.35 em, 4 gaps of 0.15 em): official box (1.08 em, 850, padding
  // 0.2/0.45 em, 2 pt border), data and model lines (650), limits (400), footer (0.7 em, A5 12 pt, line-height
  // 1.3, margin-top 0.15 em, padding-top 0.25 em, 1.2 pt rule; rule 700, meta 400, gap 0.1 em)
  const of = 1.08 * F;
  parts.gaps = 0.35 * F + 4 * 0.15 * F;
  parts.official = para(card.official, font(1.08, 850), W - 0.9 * of - 2 * BORDER2PT) + 0.4 * of + 2 * BORDER2PT;
  parts.data = para(card.dataLine, font(1, 650), W);
  parts.model = para(card.modelLine, font(1, 650), W);
  parts.limits = para(card.limits, font(1, 400), W);
  const fs = small ?? 0.7;
  const ff = fs * F;
  // A5: the provenance line is 10 pt
  const ms = size === 'a5' ? (10 * PT_PX) / F : fs;
  parts.foot = 0.15 * F + 0.25 * ff + BORDER1_2PT + para(card.footer, font(fs, 700), W, 1.3) + para(card.meta, font(ms, 400), W, 1.3) + 0.1 * ff;
  const usedPx = Object.values(parts).reduce((a, x) => a + x, 0);
  return { usedPx, availablePx: H, parts };
}
