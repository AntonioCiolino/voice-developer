import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: process.env.VOICE_DEVELOPER_HOST || "127.0.0.1",
    port: 5773,
    strictPort: true,
  },
});
