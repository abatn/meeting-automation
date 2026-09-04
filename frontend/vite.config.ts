import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// Patched livekit-client bundle (see patches/README.md).
// Root cause: livekit-server v1.9.0 does not echo offer ids in answers (every
// answer carries id=0), but PCTransportManager.negotiate() only clears its
// hardcoded 15s negotiation deadline on OfferAnswered(offerId > checkpoint) — so
// the deadline always fired at exactly 15s -> NegotiationError ->
// CLIENT_REQUEST_LEAVE. The patched copy resolves the deadline on the legacy
// id-0 sentinel. Regenerate after upgrading the SDK:
//   python3 patches/patch-livekit-client.py
const livekitPatchedEntry = fileURLToPath(
  new URL('./patches/livekit-client.esm.mjs', import.meta.url),
)

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      // Regex anchors to the exact package specifier only, so subpath imports
      // like 'livekit-client/e2ee-worker' are NOT redirected to the patched file.
      { find: /^livekit-client$/, replacement: livekitPatchedEntry },
    ],
  },
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
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
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
