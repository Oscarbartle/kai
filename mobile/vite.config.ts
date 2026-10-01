import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// In production the app is served by kai-server from the same address as
// the API, so every call is a plain relative URL (`/pantry`, ...) and
// there's no CORS to configure. `npm run dev` keeps that property by
// proxying those same paths to a running kai-server, so the code is
// identical in both places.
const api = process.env.KAI_API ?? 'http://127.0.0.1:8799';
const apiPaths = ['/pantry', '/recipe-book', '/status', '/health'];

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: Object.fromEntries(apiPaths.map((p) => [p, { target: api, changeOrigin: true }])),
  },
});
