import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: UI on :5173, API (uvicorn) on :8000
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8010" } },
});
