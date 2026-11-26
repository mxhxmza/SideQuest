import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "SideQuest · Route-aware Stop Planner",
        short_name: "SideQuest",
        description: "Plan stops along your Singapore trip, ranked by extra minutes added.",
        theme_color: "#070b1a",
        background_color: "#070b1a",
        display: "standalone",
        start_url: "/plan",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        navigateFallbackDenylist: [/^\/api/],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/tiles\.openfreemap\.org\/.*/,
            handler: "StaleWhileRevalidate",
            options: { cacheName: "map-tiles", expiration: { maxEntries: 500, maxAgeSeconds: 7 * 86400 } },
          },
        ],
      },
    }),
  ],
  build: {
    rollupOptions: { output: { manualChunks: { maplibre: ["maplibre-gl"] } } },
    chunkSizeWarningLimit: 1100,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: { environment: "node" },
});
