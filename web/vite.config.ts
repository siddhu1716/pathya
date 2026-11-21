import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// Dev: the FastAPI backend runs on :8000; /api and /calls are proxied to it.
export default defineConfig({
  server: {
    host: "::",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/calls": "http://127.0.0.1:8000",
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
