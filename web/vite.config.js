import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// `npm run build:demo` makes one self-contained HTML file (../demo/hype-radar.html)
// that opens offline with a double-click: a safety net for the projector.
export default defineConfig(({ mode }) => ({
  plugins: mode === 'demo' ? [react(), viteSingleFile()] : [react()],
  base: './',
  build: mode === 'demo' ? { outDir: '../demo', emptyOutDir: false } : {},
}))
