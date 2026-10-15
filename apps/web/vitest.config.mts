import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    // Sama dengan `paths` di tsconfig.json.
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  // tsconfig memakai jsx: "preserve" (Next yang mengompilasi); di vitest
  // oxc (Vite 8) yang mengompilasi, jadi transformasinya dinyatakan di sini.
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    environment: "node",
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
