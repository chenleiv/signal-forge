import { Page, WebSocketRoute } from '@playwright/test';
import type { ThreatStats } from '../src/app/shared/models/threat.models';
import { expect, test } from './fixtures';

// The server closes an open stream with 4001 when the 8-hour session token
// expires. In a real browser: the app checks the session once (one new ticket
// request, answered 401 like an expired cookie), shows SIGNED OUT and stops.
//
// The socket is mocked with routeWebSocket: the expiry itself (server side)
// is covered by backend/tests/test_ws_session_expiry.py.
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
/** Close code for an ended or expired session. */
const WS_SESSION_ENDED = 4001;

async function stubStats(page: Page) {
  await page.route(url => url.pathname === '/api/stats', route =>
    route.request().method() === 'GET'
      ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STATS) })
      : route.fallback());
}

/** The first ticket request succeeds; every later one gets 401 (expired cookie). */
async function stubTicketThenExpired(page: Page): Promise<() => number> {
  let requests = 0;
  await page.route(url => url.pathname === '/auth/ws-ticket', route => {
    if (route.request().method() !== 'GET') return route.fallback();
    requests++;
    return requests === 1
      ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ticket: 'mock-ticket' }) })
      : route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Not authenticated' }) });
  });
  return () => requests;
}

test('session expiry on an open stream: one session check, then signed out, no reconnect loop', async ({ page }) => {
  await stubStats(page);
  const ticketRequests = await stubTicketThenExpired(page);
  const sockets: WebSocketRoute[] = [];
  await page.routeWebSocket(url => url.pathname === '/ws/threats', ws => {
    sockets.push(ws);
    ws.onMessage(message => {
      const body = JSON.parse(String(message)) as { type?: unknown };
      if (body.type === 'auth') ws.send(JSON.stringify({ type: 'ready' }));
    });
  });

  await page.goto('/settings');

  const chip = page.locator('.topbar-chip');
  await expect(chip).toHaveClass(/chip-live/);

  // The session expires: the server closes the open stream.
  await sockets[0].close({ code: WS_SESSION_ENDED, reason: 'session ended' });

  await expect(chip).toHaveClass(/chip-signed-out/);
  await expect(chip).toContainText('SIGNED OUT');

  // Well past the reconnect delay: nothing retries.
  await page.waitForTimeout(RECONNECT_DELAY_S * 2 * 1000);
  expect(ticketRequests()).toBe(2);                 // the first ticket and exactly one check
  expect(sockets).toHaveLength(1);
  await expect(chip).toHaveClass(/chip-signed-out/);
});
