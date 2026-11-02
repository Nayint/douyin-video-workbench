import { existsSync } from "node:fs";
import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

// The workbench's other 3D panels already use this local r186 runtime.
// Resolve the estate and its controls to that same browser module instance.
export default defineConfig({
  resolve: { preserveSymlinks: true, dedupe: ["three", "react", "react-dom"] },
  build: { rollupOptions: { preserveSymlinks: true, input: Object.fromEntries(Object.entries({ main: "index.html", coop: "coop.html", wangxuge: "wangxuge.html", interior: "interior.html", rooms: "interior-rooms.html" }).filter(([, path]) => existsSync(fileURLToPath(new URL(path, import.meta.url))))) } },
  plugins: [
    {
      name: "workbench-three-runtime",
      enforce: "pre",
      resolveId(source) {
        if (source === "three")
          return {
            id: "/duo/vendor/three/build/three.module.js",
            external: true,
          };
      },
    },
  ],
  optimizeDeps: {
    exclude: ["three", "three/addons/controls/OrbitControls.js"],
  },
  // Vendor modules are served unchanged from public, not pre-transformed.
  server: {
    preTransformRequests: false,
    host: "127.0.0.1",
    fs: { allow: [fileURLToPath(new URL(".", import.meta.url)), fileURLToPath(new URL("../../丧尸废城/", import.meta.url))] },
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/coop-net": { target: "http://127.0.0.1:8770", ws: true, rewrite: path => path.replace(/^\/coop-net/, "") },
      "/media": "http://127.0.0.1:8765",
      "/world-mp": { target: "http://127.0.0.1:8766", ws: true },
    },
  },
});
