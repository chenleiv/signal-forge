import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Use jsdom as the environment for all tests
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        // Enable localStorage support in jsdom
        storageQuota: 10_000_000,
      },
    },
    // Provide a localStorage mock for Node 26+ where native localStorage is unavailable
    setupFiles: ['./src/test-setup.ts'],
  },
});
