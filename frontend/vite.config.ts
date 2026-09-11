/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
  // loadEnv is required here because Vite does not automatically copy .env
  // values into process.env while vite.config.ts is being evaluated.
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget =
    env.API_PROXY_TARGET ||
    env.VITE_API_BASE_URL ||
    "http://localhost:8000";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/test-setup.ts",
      css: true,
    },
  };
});
