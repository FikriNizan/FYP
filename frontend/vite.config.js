import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // The browser talks to Vite at 5173; Vite forwards /api to Flask at 5000.
  server: { proxy: { '/api': { target: 'http://127.0.0.1:5000', changeOrigin: false } } },
  test: { environment: 'jsdom', include: ['tests/**/*.test.jsx'], setupFiles: ['./tests/setup.js'] },
});
