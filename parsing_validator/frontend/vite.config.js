import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The build is committed in ../web and served by the Python service (OQ-10); `npm run dev` proxies the API.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { outDir: '../web', emptyOutDir: true, sourcemap: false },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8765' } },
});
