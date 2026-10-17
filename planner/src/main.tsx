import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/app.css';
import './styles/map-hangul-fonts.css';
import { App } from './App';
import { loadHangulMapFonts } from './map/hangulFonts';

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
