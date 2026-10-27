import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5187,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8187" },
  },
  test: {
    testTimeout: 20000,
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.d.ts", "src/**/*.test.{ts,tsx}", "src/test-setup.ts"],
      reporter: ["text", "json-summary", "lcov"],
      thresholds: { lines: 90, branches: 90 },
    },
  },
});
