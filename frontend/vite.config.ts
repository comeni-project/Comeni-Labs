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
    proxy: { "/api": "http://localhost:8000" },
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
