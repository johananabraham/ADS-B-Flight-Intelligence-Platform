import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

function runtimeApp(staticMode: boolean): Plugin {
  const virtualId = 'virtual:runtime-app'
  const resolvedId = `\0${virtualId}`
  return {
    name: 'runtime-app',
    resolveId(id) {
      return id === virtualId ? resolvedId : undefined
    },
    load(id) {
      if (id !== resolvedId) return undefined
      const target = staticMode ? '/src/StaticEvidenceApp.tsx' : '/src/App.tsx'
      return `export { default } from ${JSON.stringify(target)}`
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const staticMode = env.VITE_RUNTIME_MODE === 'STATIC_EVIDENCE'
  return {
  define: {
    'import.meta.env.VITE_DATA_SOURCE_MODE': JSON.stringify(env.VITE_DATA_SOURCE_MODE || 'LIVE RF'),
  },
  plugins: [runtimeApp(staticMode), react()],
  build: {
    modulePreload: { polyfill: !staticMode },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  }
})
