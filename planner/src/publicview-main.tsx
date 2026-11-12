import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { appDirPath } from './config/paths';
import { installFetchGuard } from './config/sameOrigin';
import { applyTokens } from './features/publicview/applyTokens';
import { PublicView } from './features/publicview/PublicView';
import './features/publicview/publicview.css';

// Replay prototype: nothing may leave the page's origin, in every build mode.
installFetchGuard({ block: true, appDir: appDirPath() });
const dark = typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches;
applyTokens(document.documentElement, dark);
const root = document.getElementById('root');
if (!root) throw new Error('#root missing');
createRoot(root).render(
  <StrictMode>
    <PublicView />
  </StrictMode>,
);
