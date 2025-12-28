import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true, // Ensures server listens on network
    port: 3000,
    
    // --- FIX START ---
    // This allows the specific ngrok URL to access the server
    allowedHosts: [
      'unsubmissive-kina-spacially.ngrok-free.dev'
    ],
    // --- FIX END ---

    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})