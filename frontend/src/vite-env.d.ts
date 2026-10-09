/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend base URL; empty in development (the dev server proxies). */
  readonly VITE_API_URL?: string;
  /** Household shown until sign-in exists. Default CUST001. */
  readonly VITE_CUSTOMER_ID?: string;
  /** That household's meter. Default MTR001. */
  readonly VITE_METER_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
