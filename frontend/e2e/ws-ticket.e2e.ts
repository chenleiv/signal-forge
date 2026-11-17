import { Page } from '@playwright/test';
import type { ThreatStats } from '../src/app/shared/models/threat.models';
import { expect, test } from './fixtures';

// The WebSocket ticket travels as the first message, so the server accepts
// the socket before it checks the ticket, and a rejected ticket now reaches
// the browser as close code 4001 (before, the pre-accept close showed as
// 1006). The app must check the session once, then show SIGNED OUT and stop.
//
// Rate limits: GET /auth/ws-ticket and GET /api/stats are stubbed, so this
// spec sends neither to the server and uses none of their per-IP limits.

const STATS: ThreatStats = {
  severity_counts: { critical: 0, high: 0, medium: 0, low: 0 },
  attack_types: {},
  events_per_min: [],
  top_ips: [],
};

/** Seconds; the app's default reconnect delay. */
const RECONNECT_DELAY_S = 3;

async function stubStats(page: Page) {
  await page.route(url => url.pathname === '/api/stats', route =>
    route.request().method() === 'GET'
      ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STATS) })
      : route.fallback());
}

/** Every ticket request gets a well-formed answer with a ticket the server rejects. */
async function stubInvalidTicket(page: Page): Promise<() => number> {
  let requests = 0;
  await page.route(url => url.pathname === '/auth/ws-ticket', route => {
    if (route.request().method() !== 'GET') return route.fallback();
    requests++;
    return route.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ ticket: 'not-a-valid-ticket' }),
    });
  });
  return () => requests;
}

test('a rejected ws ticket: one session check, then signed out, no reconnect loop', async ({ page }) => {
  await stubStats(page);
  const ticketRequests = await stubInvalidTicket(page);
  const socketUrls: string[] = [];
  page.on('websocket', ws => socketUrls.push(ws.url()));

  await page.goto('/settings');

  const chip = page.locator('.topbar-chip');
  await expect(chip).toHaveClass(/chip-signed-out/);
  await expect(chip).toContainText('SIGNED OUT');

  // Well past the reconnect delay: nothing retries.
  await page.waitForTimeout(RECONNECT_DELAY_S * 2 * 1000);
  expect(ticketRequests()).toBe(2);                 // the first ticket and exactly one check
  expect(socketUrls).toHaveLength(2);
  for (const url of socketUrls) expect(url).not.toContain('ticket');
  await expect(chip).toHaveClass(/chip-signed-out/);
});
