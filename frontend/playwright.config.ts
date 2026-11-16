import { defineConfig } from '@playwright/test';

/**
 * End-to-end layout checks (npm run e2e). Starts its own server (e2e/serve.mjs):
 * the production build served by the backend in demo mode, like on Render.
 */
const port = Number(process.env['E2E_PORT'] ?? 8765);

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  workers: 1,               // one server, and login is rate limited per IP
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: 'chromium',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'phone',
      dependencies: ['setup'],
      use: {
        storageState: 'e2e/.auth/admin.json',
        viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3,
      },
    },
    {
      // A touch tablet (iPad Air portrait). Same slide-in menu as a phone, so
      // the phone menu tests run here too; Detection Rules keeps two panes on
      // a tablet, so the phone-only one-pane rules test is left out.
      // `npm run e2e` runs this project in its own pass (fresh server): in one
      // pass with phone and desktop, the page loads exceed the 50/minute
      // per-IP limit on /api/stats and the threats table stays empty.
      name: 'tablet',
      dependencies: ['setup'],
      grepInvert: /phone rules/,
      use: {
        storageState: 'e2e/.auth/admin.json',
        viewport: { width: 820, height: 1180 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2,
      },
    },
    {
      name: 'desktop',
      dependencies: ['setup'],
      use: { storageState: 'e2e/.auth/admin.json', viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: {
    command: 'node e2e/serve.mjs',
    url: `http://127.0.0.1:${port}/health`,
    reuseExistingServer: false,
    timeout: 240_000,
  },
});
