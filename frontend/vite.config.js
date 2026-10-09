import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { VitePWA } from 'vite-plugin-pwa';

const BG = '#0b1a10';
// La versión sale de package.json; el hook pre-commit la sube en cada commit
const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  plugins: [
    svelte(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      registerType: 'autoUpdate',
      injectRegister: false,
      injectManifest: {
        // Los splash de iOS solo se usan al instalar: no se precachean
        globPatterns: ['**/*.{js,css,html,webp,woff2}', 'icons/icon-192.png', 'favicon.png'],
      },
      manifest: {
        id: '/',
        name: 'Ancares Seguidores',
        short_name: 'Ancares',
        description: 'Clasificación, calendario y resultados del CDF Voleibol Ancares (app no oficial).',
        lang: 'es',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: BG,
        theme_color: BG,
        categories: ['sports'],
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
        shortcuts: [{ name: 'Club y feedback', url: '/#/club', icons: [{ src: '/icons/icon-192.png', sizes: '192x192' }] }],
        // Permite "Compartir → Ancares" con los Excel de la federación (Android)
        share_target: {
          action: '/share-target',
          method: 'POST',
          enctype: 'multipart/form-data',
          params: {
            title: 'title',
            text: 'text',
            files: [
              {
                name: 'files',
                accept: ['application/vnd.ms-excel', 'application/octet-stream', 'application/x-msexcel', '.xls'],
              },
            ],
          },
        },
      },
    }),
  ],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  preview: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    target: 'es2020',
    cssCodeSplit: true,
  },
});
