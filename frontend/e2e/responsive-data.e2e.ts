import { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import type {
  AlertSummaryMetrics, Incident, ThreatAlert,
} from '../src/app/shared/models/threat.models';

// Data pages around the breakpoints: $narrow (768px) and $tablet (1024px).
// Every test starts logged in as the demo admin (see auth.setup.ts).
//
// Alerts and incidents come from slower rules and stay empty for a while on
// the test server, so the tests that open their details stub only these three
// GET requests (alerts list, alerts summary, incidents list) with fixed data
// in the shape of the real API types. Everything else is the real server.

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

const ALERTS: ThreatAlert[] = [
  {
    id: 'ALR-1001', source: 'behavioral', detection_source: 'behavioral_detection',
    type: 'BruteForce', severity: 'critical', ip: '185.220.101.34',
    country: 'Russia', country_code: 'RU', affected_asset: 'vpn-gw-01',
    mitre_technique: 'T1110', confidence_score: 92, risk_score: 88,
    message: 'Repeated failed SSH logins from one source within 10 minutes',
    status: 'new', created_at: minutesAgo(3), acknowledged_at: null,
    event_timeline: [
      { event: 'Detection', description: 'Login failure rate above baseline', type: 'detection', at: minutesAgo(5) },
      { event: 'Alert raised', description: 'Behavioral threshold crossed', type: 'alert', at: minutesAgo(3) },
    ],
  },
  {
    id: 'ALR-1002', source: 'rule', detection_source: 'sigma_rule',
    type: 'SQLi', severity: 'high', ip: '45.155.205.12',
    country: 'Netherlands', country_code: 'NL', affected_asset: 'web-app-02',
    mitre_technique: 'T1190', confidence_score: 78, risk_score: 71,
    message: 'SQL injection pattern in a login form parameter',
    status: 'acknowledged', created_at: minutesAgo(20), acknowledged_at: minutesAgo(12),
    event_timeline: [
      { event: 'Attempt', description: 'UNION SELECT payload on /login', type: 'attempt', at: minutesAgo(21) },
    ],
  },
];

const SUMMARY: AlertSummaryMetrics = {
  active_threats: 14, critical_alerts: 3, mttr_min: 27,
  top_attack_type: 'BruteForce', blocked_indicators: 9,
};

const INCIDENTS: Incident[] = [
  {
    id: 'INC-2001', title: 'Brute force against the VPN gateway', severity: 'critical',
    status: 'investigating', attack_type: 'BruteForce', source_ip: '185.220.101.34',
    source_region: 'RU', event_count: 42, assigned_to: 'admin',
    created_at: minutesAgo(60), updated_at: minutesAgo(10),
    mitre_tags: ['T1110', 'T1078'],
    notes: [{ author: 'admin', text: 'Source blocked at the edge firewall.', at: minutesAgo(15) }],
    completed_tasks: [0],
  },
];

async function stubData(page: Page) {
  const json = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  await page.route(url => url.pathname === '/api/alerts', route =>
    route.request().method() === 'GET' ? route.fulfill(json(ALERTS)) : route.fallback());
  await page.route(url => url.pathname === '/api/alerts/summary', route =>
    route.request().method() === 'GET' ? route.fulfill(json(SUMMARY)) : route.fallback());
  await page.route(url => url.pathname === '/api/incidents', route =>
    route.request().method() === 'GET' ? route.fulfill(json(INCIDENTS)) : route.fallback());
}

type Box = { x: number; y: number; width: number; height: number };
const box = async (page: Page, selector: string): Promise<Box> =>
  (await page.locator(selector).first().boundingBox())!;

/** Horizontal overflow of an element: scrollWidth beyond clientWidth. */
const overflowX = (page: Page, selector: string) =>
  page.locator(selector).first().evaluate(el => el.scrollWidth - el.clientWidth);

const isPhone = (page: Page, isMobile: boolean) => isMobile && page.viewportSize()!.width <= 768;
const isTablet = (page: Page, isMobile: boolean) => {
  const w = page.viewportSize()!.width;
  return isMobile && w > 768 && w <= 1024;
};

// ── Phones ────────────────────────────────────────────────────

test('phone: the map filters fit at 390px with 44px touch targets', async ({ page, isMobile }) => {
  test.skip(!isPhone(page, isMobile), 'phone only');
  await page.goto('/map');
  const buttons = page.locator('.map-page .filter-bar .filter-btn');
  await expect(buttons).toHaveCount(5);
  expect(await overflowX(page, '.map-page .filter-bar')).toBeLessThanOrEqual(0);
  const width = page.viewportSize()!.width;
  for (const b of await buttons.all()) {
    const r = (await b.boundingBox())!;
    expect(r.x + r.width).toBeLessThanOrEqual(width);
    expect(r.height).toBeGreaterThanOrEqual(44);
  }
});

test('phone: the alerts filters wrap above the list and the metrics fit', async ({ page, isMobile }) => {
  test.skip(!isPhone(page, isMobile), 'phone only');
  await stubData(page);
  await page.goto('/alerts');
  await page.locator('.alert-card:not(.sk-card)').first().waitFor();
  await page.locator('.soc-metrics').waitFor();

  const width = page.viewportSize()!.width;
  const filters = await box(page, '.filter-panel');
  const main = await box(page, '.alerts-main');
  expect(filters.width).toBeGreaterThanOrEqual(width - 1);     // a full-width row
  expect(filters.y + filters.height).toBeLessThanOrEqual(main.y + 1);   // above the list
  expect(main.width).toBeGreaterThanOrEqual(width - 1);
  expect(await overflowX(page, '.soc-metrics')).toBeLessThanOrEqual(0);
  expect(await overflowX(page, '.filter-panel')).toBeLessThanOrEqual(0);

  // Chips: at least 32px tall, with a clear gap between neighbours on a line.
  const chips = await page.locator('.filter-panel .filter-section').nth(1).locator('.filter-btn').all();
  const rects = await Promise.all(chips.map(async c => (await c.boundingBox())!));
  for (const r of rects) {
    expect(r.height).toBeGreaterThanOrEqual(32);
    expect(r.x + r.width).toBeLessThanOrEqual(width);
  }
  for (let i = 1; i < rects.length; i++) {
    if (Math.abs(rects[i].y - rects[i - 1].y) < 1) {
      expect(rects[i].x - (rects[i - 1].x + rects[i - 1].width)).toBeGreaterThanOrEqual(8);
    }
  }
});

test('phone: incident detail has a 44px close button, wrapping status buttons and one meta column', async ({ page, isMobile }) => {
  test.skip(!isPhone(page, isMobile), 'phone only');
  await stubData(page);
  await page.goto('/incidents');
  await page.locator('tr.inc-row').first().click();
  await page.waitForTimeout(400);                    // slide-in animation

  const close = await box(page, '.drawer-overlay.open .close-btn');
  expect(close.width).toBeGreaterThanOrEqual(44);
  expect(close.height).toBeGreaterThanOrEqual(44);

  expect(await overflowX(page, '.drawer-overlay.open .status-bar')).toBeLessThanOrEqual(0);
  await expect(page.locator('.drawer-overlay.open .status-arrow').first()).toBeHidden();

  const columns = await page.locator('.drawer-overlay.open .meta-grid')
    .evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
  expect(columns).toBe(1);
});

// ── Tablets ───────────────────────────────────────────────────

test('tablet: the alerts drawer opens over the list and fits', async ({ page, isMobile }) => {
  test.skip(!isTablet(page, isMobile), 'tablet only');
  await stubData(page);
  await page.goto('/alerts');
  const card = page.locator('.alert-card:not(.sk-card)').first();
  await card.waitFor();
  const before = await box(page, '.alerts-main');

  await card.click();
  await page.locator('.drawer-panel').waitFor();
  const width = page.viewportSize()!.width;
  const drawer = await box(page, '.drawer-panel');
  const after = await box(page, '.alerts-main');

  expect(drawer.width).toBeLessThanOrEqual(width * 0.9 + 1);
  expect(drawer.x + drawer.width).toBeLessThanOrEqual(width + 1);
  expect(after.width).toBeGreaterThanOrEqual(before.width - 1);   // the list keeps its width

  const close = await box(page, '.drawer-panel .close-btn');
  expect(close.width).toBeGreaterThanOrEqual(44);
  expect(close.height).toBeGreaterThanOrEqual(44);
});

test('tablet: the dashboard charts form a 2x2 grid and the stream keeps 300px', async ({ page, isMobile }) => {
  test.skip(!isTablet(page, isMobile), 'tablet only');
  await page.goto('/dashboard');
  const panels = page.locator('.chart-row > .panel');
  await expect(panels).toHaveCount(4);
  const r = await Promise.all((await panels.all()).map(async p => (await p.boundingBox())!));
  expect(Math.abs(r[0].y - r[1].y)).toBeLessThan(1);   // first row
  expect(Math.abs(r[2].y - r[3].y)).toBeLessThan(1);   // second row
  expect(r[2].y).toBeGreaterThan(r[0].y + r[0].height - 1);
  expect(r[1].x).toBeGreaterThan(r[0].x);
  expect((await box(page, '.stream-panel')).height).toBeGreaterThanOrEqual(300);
});

// ── Phones and tablets ────────────────────────────────────────

test('threat table: the filters and header fit the screen', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'phone and tablet');
  await page.goto('/threats');
  await page.locator('.threat-table-wrapper .table-header').waitFor();
  expect(await overflowX(page, '.threat-table-wrapper .filter-bar')).toBeLessThanOrEqual(0);
  expect(await overflowX(page, '.threat-table-wrapper .table-header')).toBeLessThanOrEqual(0);
});

// ── Desktop guard ─────────────────────────────────────────────

test.describe('desktop at 1025px', () => {
  test.skip(({ isMobile }) => !!isMobile, 'resizes a desktop browser');

  test('the alerts filters stay a 160px column beside the list', async ({ page }) => {
    await page.setViewportSize({ width: 1025, height: 768 });
    await stubData(page);
    await page.goto('/alerts');
    await page.locator('.alert-card:not(.sk-card)').first().waitFor();
    const filters = await box(page, '.filter-panel');
    const main = await box(page, '.alerts-main');
    expect(Math.round(filters.width)).toBe(160);
    expect(main.x).toBeGreaterThanOrEqual(filters.x + filters.width - 1);
    expect(Math.abs(main.y - filters.y)).toBeLessThan(1);

    // The drawer still sits beside the list, not over it.
    await page.locator('.alert-card:not(.sk-card)').first().click();
    await page.locator('.drawer-panel').waitFor();
    const position = await page.locator('.drawer-panel').evaluate(el => getComputedStyle(el).position);
    expect(position).toBe('relative');
  });

  test('the dashboard charts stay four across', async ({ page }) => {
    await page.setViewportSize({ width: 1025, height: 768 });
    await page.goto('/dashboard');
    const panels = page.locator('.chart-row > .panel');
    await expect(panels).toHaveCount(4);
    const r = await Promise.all((await panels.all()).map(async p => (await p.boundingBox())!));
    for (const p of r) expect(Math.abs(p.y - r[0].y)).toBeLessThan(1);
  });
});
