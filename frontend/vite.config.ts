import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
// `vitest/config`, not `vite`: the `test` block below is vitest's, and vite's own
// `defineConfig` does not know the key. `npx tsc --noEmit` never noticed — `tsc -b`
// uses the project references and does, which is why `npm run build` is the gate.
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The API is a separate process; the browser talks to one origin.
    // One prefix, so the SPA keeps every other path — including its own `/forge/*` routes,
    // which this proxy used to swallow.
    // **Two APIs, one origin, split by path.** Wiener is its own service and its routes live
    // under `/api` too (spec §13), so the specific entries come FIRST — vite matches in
    // insertion order and `/api` would otherwise swallow both.
    //
    // **Wiener is reached through nginx, not through a port.** These pointed at
    // `localhost:8001` and `wiener-api` publishes no host port by design — its compose entry
    // says so in as many words — so every Wiener route on the HMR server was a 502 while the
    // same route through `http://localhost/` was fine. `make dev` prints the HMR address
    // first, so the advertised way in was the one where half the app was dead.
    //
    // Proxying at nginx rather than opening 8001 is the fix that keeps the decision: dev now
    // takes the path prod serves, WebSocket upgrade and the 512m artifact body included,
    // which is the whole argument `docker-compose.prod.yml` makes for being an overlay.
    proxy: {
      "/api/runs": { target: "http://localhost", ws: true },
      "/api/artifacts": "http://localhost",
      "/api": "http://localhost:8000",
    },
  },
  test: {
    // happy-dom rather than jsdom: jsdom pulls @asamuzakjp/css-color, which require()s
    // an ES module and dies under Node 22 in every vitest pool. happy-dom has no such
    // chain and these are component tests, not browser-fidelity tests.
    environment: "happy-dom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});
