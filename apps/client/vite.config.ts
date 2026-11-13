import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The client is a plain SPA: the same `dist/` is loaded by Electron and by the
// Capacitor WebView, so every path must be relative ("base: './'").
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false },
});
