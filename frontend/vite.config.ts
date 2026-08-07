import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          mui: ['@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled'],
          recharts: ['recharts'],
          redux: ['@reduxjs/toolkit', 'react-redux'],
        }
      }
    }
  },
  server: {
    // TEMPORARY for local test against staging (2026-08-06): port 3001 because
    // an unrelated process (HEIMAT) occupies 3000. Proxy targets the STAGING
    // backend so the new Recording-Start-Guard can be tested against the real
    // Helm pipeline. REVERT after test: cp /tmp/vite.config.ts.original frontend/vite.config.ts
    port: 3001,
    proxy: {
      '/api': {
        target: 'https://staging.meeting-automation.com',
        secure: false,
        changeOrigin: true,
        timeout: 600000, // 10 minutes
        proxyTimeout: 600000,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            // Log outgoing requests for easier debugging
            if (req.method === 'POST') {
               console.log('Proxying POST request to:', req.url);
            }
          });
        },
      },
    },
  },
})
