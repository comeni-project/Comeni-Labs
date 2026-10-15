import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
// Vitest's defineConfig types both the Vite application and the test configuration.
import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const root = fileURLToPath(new URL("../", import.meta.url));
  const env = { ...loadEnv(mode, root, ""), ...process.env };
  const api = `http://127.0.0.1:${env.API_HOST_PORT || "8000"}`;
  const web = `http://127.0.0.1:${env.WEB_HOST_PORT || "80"}`;
  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: "127.0.0.1",
      port: Number(env.VITE_HOST_PORT || "5173"),
      strictPort: true,
      // Proxy only /api paths; browser routes such as /forge remain with the application.
      // Specific Wiener prefixes precede Mendel's catch-all because matching uses insertion order.
      // Wiener is reached through nginx, which forwards WebSockets and artifact uploads.
      // Make supplies Compose's parsed environment, including configured host ports.
      proxy: {
        "/api/runs": { target: web, ws: true },
        "/api/artifacts": web,
        "/api/wiener": web,
        "/api": api,
      },
    },
    test: {
      // Component tests use a simulated DOM. setupTests supplies dimensions for virtualized lists.
      environment: "happy-dom",
      globals: true,
      setupFiles: "./src/setupTests.ts",
    },
  };
});
