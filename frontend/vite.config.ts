import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'es2021',
    sourcemap: true,
    rollupOptions: { output: { manualChunks: { ol: ['ol', 'proj4'], react: ['react', 'react-dom', 'zustand'] } } },
  },
  server: { port: 5173 },
});
