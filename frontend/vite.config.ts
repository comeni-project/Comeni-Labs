import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The API is a separate process; the browser talks to one origin.
    proxy: { "/questions": "http://localhost:8000", "/health": "http://localhost:8000",
             "/forge": "http://localhost:8000" },
  },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/setupTests.ts" },
});
