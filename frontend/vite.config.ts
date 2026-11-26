/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // Not Vite's default 5173: Windows (Hyper-V / WSL) often reserves 5141-5240, and a reserved
    // port fails with EACCES instead of moving on to the next free one.
    port: 3000,
    // The FastAPI backend (see backend/src/server.py).
    proxy: { '/api': 'http://localhost:8000' },
  },
  // Vitest (`npm run test`); see docs/frontend-tests/plan.md.
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    unstubGlobals: true,
  },
})
