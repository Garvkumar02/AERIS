import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/admin-portal/',
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/devices': 'http://127.0.0.1:8000',
      '/biometric': 'http://127.0.0.1:8000',
      '/attendance': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/registry': 'http://127.0.0.1:8000',
      '/gate': 'http://127.0.0.1:8000',
    },
  },
})
