import { test as base } from '@playwright/test';

/**
 * Tests talk only to the local test server: any other HTTP request is
 * aborted and any other WebSocket is closed, so a test can never reach the
 * real deployment (or any third party).
 */
export const test = base.extend({
  context: async ({ context, baseURL }, use) => {
    const local = new URL(baseURL!).host;
    await context.route(url => url.host !== local, route => route.abort());
    await context.routeWebSocket(url => url.host !== local, ws => ws.close());
    await use(context);
  },
});

export { expect } from '@playwright/test';
