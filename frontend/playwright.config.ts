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
