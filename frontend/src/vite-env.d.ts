/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend base URL; empty in development (the dev server proxies). */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
