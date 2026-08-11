import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // tests/e2e/**  is Playwright's suite (npm run test:e2e), not vitest's --
    // it uses its own test()/expect() from @playwright/test, which conflicts
    // with vitest's globals if collected here.
    exclude: ["node_modules/**", "tests/e2e/**"],
  },
});
