import { defineConfig } from "vite";
import { sveltekit } from "@sveltejs/kit/vite";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [sveltekit()],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    // Bind IPv4 loopback explicitly. Node's default "localhost" binding
    // resolves IPv6-only on this machine ([::1] but no 127.0.0.1 listener),
    // and the webview's dual-stack fallback when navigating to
    // http://localhost:1420 was adding a ~27s stall before it fell back
    // to IPv6. Pinning both this and tauri.conf.json's devUrl to
    // 127.0.0.1 removes the ambiguity.
    host: host || "127.0.0.1",
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`, `crates`, and the
      // build output. `**/target/**` matters most: since the Cargo
      // workspace conversion (Phase B), the actual build output moved
      // from src-tauri's own target dir to one shared root-level
      // `target/`, a sibling of src-tauri rather than something inside
      // it — so `**/src-tauri/**` alone stopped covering it, and Vite's
      // watcher would try to watch a .dll mid-compile and crash with
      // EBUSY on Windows (confirmed live: "beforeDevCommand terminated
      // with a non-zero status code").
      ignored: ["**/src-tauri/**", "**/crates/**", "**/target/**"],
    },
  },
}));
