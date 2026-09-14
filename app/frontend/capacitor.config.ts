import type { CapacitorConfig } from "@capacitor/cli";

// Native wrapper config. Do NOT run `npx cap add ios|android` in CI —
// see README.md ("Wrapping with Capacitor") for the manual steps.
const config: CapacitorConfig = {
  appId: "kr.wildfireguardian.app",
  appName: "산불지킴이",
  webDir: "dist",
  server: {
    // Native builds talk to the deployed gateway over HTTPS.
    // For local device testing point this at your dev machine, e.g.:
    // url: "http://192.168.0.10:5173", cleartext: true
    androidScheme: "https",
  },
};

export default config;
