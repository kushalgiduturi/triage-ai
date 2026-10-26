import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the UI calls the FastAPI backend directly (CORS is enabled there).
// Set VITE_API_URL, e.g. VITE_API_URL=http://localhost:8000 npm run dev.
// In production the built files are served by FastAPI itself, so requests are same-origin.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: { port: 5173 },
});
