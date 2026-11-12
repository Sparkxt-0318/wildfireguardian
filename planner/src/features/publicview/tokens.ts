/**
 * Colour and size tokens of the public prototype (one source for the CSS and for the contrast / colour-vision tests).
 * Okabe–Ito hues for the three states; there is deliberately no green. Text sizes in px.
 */
import type { Tone } from './model';

export interface Theme {
  bg: string;
  text: string;
  muted: string;
  banner: { bg: string; text: string };
  official: { bg: string; text: string };
  /** per state: the card's accent stripe / icon colour and the text drawn on it */
  tone: Record<Tone, { accent: string; onAccent: string }>;
}

export const LIGHT: Theme = {
  bg: '#FFFFFF',
  text: '#111111',
  muted: '#333333',
  banner: { bg: '#111111', text: '#FFFFFF' },
  official: { bg: '#FFF4CC', text: '#111111' },
  tone: {
    leave: { accent: '#00426B', onAccent: '#FFFFFF' }, // dark Okabe–Ito blue
    stop: { accent: '#8A2B00', onAccent: '#FFFFFF' }, // dark vermilion
    unknown: { accent: '#4A4A4A', onAccent: '#FFFFFF' }, // grey
  },
};

export const DARK: Theme = {
  bg: '#0B0B0C',
  text: '#F5F5F5',
  muted: '#D6D6D6',
  banner: { bg: '#F5F5F5', text: '#0B0B0C' },
  official: { bg: '#3A3000', text: '#FFF4CC' },
  tone: {
    leave: { accent: '#9AD3FF', onAccent: '#0B0B0C' },
    stop: { accent: '#FFB38A', onAccent: '#0B0B0C' },
    unknown: { accent: '#C8C8C8', onAccent: '#0B0B0C' },
  },
};

export const SIZE = { base: 20, words: 24, time: 40, dataAge: 40, stamp: 24, question: 32 } as const;
