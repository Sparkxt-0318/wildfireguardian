// The close-up's fixed scale: 80 m across the 300 px card (3.75 px per metre).
import { zoomForPxPerMetre } from './mapview.js';

export const LENS_PPM = 300 / 80;
export function zoomForLens(lat) { return zoomForPxPerMetre(LENS_PPM, lat); }
