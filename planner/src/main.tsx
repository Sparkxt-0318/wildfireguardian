import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/app.css';
import './styles/map-hangul-fonts.css';
import { STATIC_DEMO } from './config/env';
import { appDirPath } from './config/paths';
import { installFetchGuard } from './config/sameOrigin';
import { App } from './App';
import { loadHangulMapFonts } from './map/hangulFonts';

// Static demo: nothing may leave the page's origin (see config/sameOrigin.ts; the build also sets a
// Content-Security-Policy). Under a sub-path base, root-absolute "/data/…" paths are moved under it.
installFetchGuard({ block: STATIC_DEMO, appDir: appDirPath() });

const root = document.getElementById('root');
if (!root) throw new Error('#root missing');
// Korean basemap labels must be drawn with the bundled Pretendard from the first frame (see hangulFonts.ts).
void loadHangulMapFonts().then(() => {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
