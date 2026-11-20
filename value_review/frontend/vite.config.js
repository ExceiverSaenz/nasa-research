import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The build goes to ../web and is served by the Python service; `npm run dev` proxies the API (port 8766).
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { outDir: '../web', emptyOutDir: true, sourcemap: false },
  server: { port: 5174, proxy: { '/api': 'http://127.0.0.1:8766' } },
});
