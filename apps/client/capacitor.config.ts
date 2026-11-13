import type { CapacitorConfig } from "@capacitor/cli";

// The Android shell loads the same Vite build as the desktop app.
const config: CapacitorConfig = {
  appId: "cloud.amigok.kaarvand",
  appName: "کاروند",
  webDir: "dist",
  android: {
    allowMixedContent: false,
  },
};

export default config;
