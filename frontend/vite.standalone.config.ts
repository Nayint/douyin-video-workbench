import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
import { cpSync, existsSync } from "node:fs";

export default defineConfig({
  define: { __VIRALLAB_STANDALONE__: "true" },
  publicDir: false,
  build: { outDir: "dist-standalone", emptyOutDir: true,
    rollupOptions: { input: fileURLToPath(new URL("index.html", import.meta.url)) } },
  plugins: [{ name: "standalone-public-assets", closeBundle() {
    for (const name of ["vendor", "licenses"]) {
      const source = fileURLToPath(new URL("./public/duo/" + name, import.meta.url));
      if (existsSync(source)) cpSync(source, fileURLToPath(new URL("./dist-standalone/duo/" + name, import.meta.url)), { recursive: true });
    }
  } }, { name: "standalone-three-runtime", enforce: "pre", resolveId(source) {
    if (source === "three") return { id: "/duo/vendor/three/build/three.module.js", external: true };
  } }],
});
