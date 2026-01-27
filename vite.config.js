import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSourceLocator } from "@metagptx/vite-plugin-source-locator";

export default defineConfig({
  plugins: [viteSourceLocator({ prefix: "mgx" }), react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        ws: true,
      },
    },
  },
});
