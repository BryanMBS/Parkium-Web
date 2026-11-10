import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El dev server de Vite hace de proxy hacia la API FastAPI: así la
// cookie de sesión vive en el mismo origen y no hay que negociar CORS.
// El puerto de la API se elige con la variable PARKIUM_API_PORT (8000 por defecto).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.PARKIUM_API_PORT ?? 8000}`,
        changeOrigin: true,
      },
    },
  },
})
