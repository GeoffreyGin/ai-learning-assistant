import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API requests to the FastAPI dev server. The frontend calls these paths
// directly (same-origin), so dev and production share one base URL.
const API_PREFIXES = [
  "/courses",
  "/passages",
  "/documents",
  "/concepts",
  "/graph",
  "/relationships",
  "/directory",
  "/learning",
  "/assessment",
  "/agent",
  "/health",
];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_PREFIXES.map((prefix) => [
        prefix,
        { target: "http://localhost:8000", changeOrigin: true },
      ]),
    ),
  },
});
