/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WFG_API_MODE?: string;
  readonly VITE_WFG_API_TARGET?: string;
  readonly VITE_DEPARTURE_STEP_MIN?: string;
  readonly VITE_SHELTERS_PER_ORIGIN?: string;
  readonly VWORLD_API_KEY?: string;
  readonly VITE_WFG_ALLOW_BATCH?: string;
  /** "/" (default), "/wildfireguardian/" (GitHub Pages) or "./" — Vite `base`; read through BASE_URL */
  readonly VITE_BASE_PATH?: string;
  /** "의견 보내기 / Feedback" link (https only) */
  readonly VITE_FEEDBACK_URL?: string;
  /** repository web URL for documentation links (https only) */
  readonly VITE_REPO_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
