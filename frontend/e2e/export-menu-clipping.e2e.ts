import { Page } from '@playwright/test';
import type { ThreatStats } from '../src/app/shared/models/threat.models';
import { expect, test } from './fixtures';

// Regression: the export menu was clipped by its table container when the
// threat table was short (one row, or none after a filter). The container
// has overflow: hidden, so on a short table only CSV and PDF showed. The live
// feed usually fills the table, which hid the bug; here /api/stats is stubbed
// with exactly one IP so the table height does not depend on the feed.
//
// Stats polling starts with the stream socket, so the ticket and the socket
// are stubbed too (as in ws-session-expiry.e2e.ts). This spec then uses none
// of the per-IP limits on /auth/ws-ticket and /api/stats, and stays
// deterministic under --repeat-each.
// Every test starts logged in as the demo admin (see auth.setup.ts).

const ONE_IP_STATS: ThreatStats = {
  severity_counts: { critical: 1, high: 0, medium: 0, low: 0 },
  attack_types: {},
  events_per_min: [],
  top_ips: [{ ip: '203.0.113.7', count: 3, score: 91, threat_level: 'critical' }],
};

const THREATS = 'app-threat-table app-export-menu';
const INCIDENTS = 'app-incidents app-export-menu';

async function stubOneIpFeed(page: Page) {
  await page.route(url => url.pathname === '/api/stats', route =>
    route.request().method() === 'GET' ? route.fulfill({ json: ONE_IP_STATS }) : route.fallback());
  await page.route(url => url.pathname === '/auth/ws-ticket', route =>
    route.request().method() === 'GET' ? route.fulfill({ json: { ticket: 'mock-ticket' } }) : route.fallback());
  await page.routeWebSocket(url => url.pathname === '/ws/threats', ws => {
    ws.onMessage(message => {
      const body = JSON.parse(String(message)) as { type?: unknown };
      if (body.type === 'auth') ws.send(JSON.stringify({ type: 'ready' }));
    });
  });
}

async function openMenu(page: Page, host: string) {
  const button = page.locator(`${host} .btn-export`);
  await button.scrollIntoViewIfNeeded();
  await button.click();
  await page.locator(`${host} .export-dropdown`).waitFor();
}

async function expectItemsVisible(page: Page, host: string) {
  const items = page.locator(`${host} .export-dropdown button`);
  await expect(items).toHaveText(['CSV', 'PDF', 'JSON', 'Markdown']);
  const view = page.viewportSize()!;
  for (const item of await items.all()) {
    const label = (await item.textContent())?.trim();
    const r = (await item.boundingBox())!;
    expect(r.x, `${label} left`).toBeGreaterThanOrEqual(0);
    expect(r.y, `${label} top`).toBeGreaterThanOrEqual(0);
    expect(r.x + r.width, `${label} right`).toBeLessThanOrEqual(view.width);
    expect(r.y + r.height, `${label} bottom`).toBeLessThanOrEqual(view.height);
    const onTop = await item.evaluate(el => {
      const b = el.getBoundingClientRect();
      return document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2) === el;
    });
    expect(onTop, `${label} is not clipped or covered`).toBe(true);
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

const PHONE_WIDTHS = [390, 360];

test.describe('export menu on a short table', () => {
  test('threat table with exactly one row', async ({ page }) => {
    await stubOneIpFeed(page);
    await page.goto('/threats');
    await expect(page.locator('app-threat-table .table-sub')).toHaveText('1 / 1 IPs');
    await expect(page.locator('app-threat-table .ip-row')).toHaveCount(1);
    await openMenu(page, THREATS);
    await expectItemsVisible(page, THREATS);
  });

  test('threat table with zero rows after a filter', async ({ page }) => {
    await stubOneIpFeed(page);
    await page.goto('/threats');
    await expect(page.locator('app-threat-table .table-sub')).toHaveText('1 / 1 IPs');
    await page.locator('app-threat-table .filter-input').fill('no-such-ip');
    await expect(page.locator('app-threat-table .table-sub')).toHaveText('0 / 1 IPs');
    await openMenu(page, THREATS);
    await expectItemsVisible(page, THREATS);
  });

  test('incidents with zero rows after a filter', async ({ page }) => {
    await stubOneIpFeed(page);
    await page.goto('/incidents');
    await page.locator('app-incidents .filter-input').fill('no-such-incident');
    await expect(page.locator('app-incidents .inc-row')).toHaveCount(0);
    await openMenu(page, INCIDENTS);
    await expectItemsVisible(page, INCIDENTS);
  });

  for (const width of PHONE_WIDTHS) {
    test(`phone: threat table with one row at ${width}px`, async ({ page, isMobile }) => {
      test.skip(!(isMobile && page.viewportSize()!.width <= 768), 'phone only');
      await page.setViewportSize({ width, height: 780 });
      await stubOneIpFeed(page);
      await page.goto('/threats');
      await expect(page.locator('app-threat-table .ip-row')).toHaveCount(1);
      await openMenu(page, THREATS);
      await expectItemsVisible(page, THREATS);
    });
  }

  test('keyboard: Tab reaches every item in order, and an outside click closes the menu', async ({ page }) => {
    await stubOneIpFeed(page);
    await page.goto('/threats');
    await expect(page.locator('app-threat-table .ip-row')).toHaveCount(1);
    const button = page.locator(`${THREATS} .btn-export`);
    await button.focus();
    await page.keyboard.press('Enter');
    const items = page.locator(`${THREATS} .export-dropdown button`);
    await expect(items).toHaveCount(4);
    for (const label of ['CSV', 'PDF', 'JSON', 'Markdown']) {
      await page.keyboard.press('Tab');
      await expect(page.locator(':focus')).toHaveText(label);
    }
    await page.locator('app-threat-table .table-title').click();
    await expect(page.locator(`${THREATS} .export-dropdown`)).toHaveCount(0);
  });
});
