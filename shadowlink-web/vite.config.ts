import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      // Forward AI requests to Java Gateway instead of directly to Python
      // (Jarvis routes /api/v1/jarvis/* are caught by the generic /api rule below,
      //  which forwards to the Java Gateway JarvisProxyController → Python :8000)
      '/api/ai': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      // Keep direct access for setting routes that aren't mapped in Java yet
      '/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Other Java backend APIs
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:8080',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          state: ['zustand', '@tanstack/react-query', 'immer'],
          ui: ['framer-motion', 'lucide-react'],
          markdown: ['react-markdown', 'remark-gfm', 'remark-math', 'rehype-katex'],
        },
      },
    },
  },
})
