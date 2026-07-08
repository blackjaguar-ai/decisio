import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Semana 2 — dev server con proxy a FastAPI (localhost:8000). En producción
// (Semana 3, Nginx) esto lo reemplaza el reverse proxy del VPS — ver
// Roadmap §10; por ahora esto es lo que corre con `npm run dev`.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/decision": "http://localhost:8000",
      "/cases": "http://localhost:8000",
      "/trace": "http://localhost:8000",
      "/metrics": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
