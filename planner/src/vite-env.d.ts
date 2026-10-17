/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WFG_API_MODE?: string;
  readonly VITE_WFG_API_TARGET?: string;
  readonly VITE_DEPARTURE_STEP_MIN?: string;
  readonly VITE_SHELTERS_PER_ORIGIN?: string;
  readonly VWORLD_API_KEY?: string;
  readonly VITE_WFG_ALLOW_BATCH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
