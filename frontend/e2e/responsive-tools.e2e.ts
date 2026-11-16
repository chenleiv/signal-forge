import { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import type { HuntResult, SavedHunt } from '../src/app/shared/models/threat.models';

// Tool pages (hunting, rules, settings, users, login) and the console toggle
// around the breakpoints: $narrow (768px) and $tablet (1024px).
// Every test starts logged in as the demo admin (see auth.setup.ts), except
// the login tests, which start signed out.
//
// The hunting tests stub only GET /api/hunt and GET /api/hunts with fixed
// data in the shape of the real API types, so they do not wait for the live
// stream and the saved hunts list is long enough to need its own scroll.

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

const RESULTS: HuntResult[] = Array.from({ length: 12 }, (_, i) => ({
  ip: `185.220.101.${10 + i}`, score: 90 - i * 3,
  threat_level: i < 3 ? 'critical' : i < 6 ? 'high' : i < 9 ? 'medium' : 'low',
  attack_type: i % 2 ? 'BruteForce' : 'SQLi',
  region: 'RU', timestamp: minutesAgo(i),
}));

const SAVED: SavedHunt[] = Array.from({ length: 25 }, (_, i) => ({
  id: `hunt-${i + 1}`, name: `Saved hunt number ${i + 1}`,
  query: { min_score: 50 + i, max_score: 100 }, created_at: minutesAgo(i * 5), result_count: 10 + i,
}));

async function stubHunting(page: Page) {
  const json = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  await page.route(url => url.pathname === '/api/hunt', route =>
    route.request().method() === 'GET' ? route.fulfill(json({ results: RESULTS, total: RESULTS.length })) : route.fallback());
  await page.route(url => url.pathname === '/api/hunts', route =>
    route.request().method() === 'GET' ? route.fulfill(json(SAVED)) : route.fallback());
}

async function runHunt(page: Page) {
  await stubHunting(page);
  await page.goto('/hunting');
  await page.locator('.saved-item').first().waitFor();
  await page.locator('.query-actions .btn-run').click();
  await page.locator('.results-table tbody tr').first().waitFor();
}

type Box = { x: number; y: number; width: number; height: number };
const box = async (page: Page, selector: string): Promise<Box> =>
  (await page.locator(selector).first().boundingBox())!;

/** Every matching visible element is at least `min` px tall (and wide, if `square`). */
async function expectTargets(page: Page, selector: string, min: number, square = false) {
  await page.locator(selector).first().waitFor();
  const items = await page.locator(selector).all();
  for (const item of items) {
    const r = (await item.boundingBox())!;
    expect(r.height, selector).toBeGreaterThanOrEqual(min);
    if (square) expect(r.width, selector).toBeGreaterThanOrEqual(min);
  }
}

const isPhone = (page: Page, isMobile: boolean) => isMobile && page.viewportSize()!.width <= 768;

// ── Phones ────────────────────────────────────────────────────

test('phone: hunting stacks the query above results at least 300px wide', async ({ page, isMobile }) => {
  test.skip(!isPhone(page, isMobile), 'phone only');
  await runHunt(page);
  const width = page.viewportSize()!.width;
  const query = await box(page, '.hunt-sidebar');
  const results = await box(page, '.hunt-results');
  expect(results.width).toBeGreaterThanOrEqual(300);
  expect(results.width).toBeGreaterThanOrEqual(width - 1);
  expect(results.y).toBeGreaterThanOrEqual(query.y + query.height - 1);   // below the query panel
  expect(query.width).toBeGreaterThanOrEqual(width - 1);
});

test('phone: a long saved hunts list scrolls on its own and the results stay in view', async ({ page, isMobile }) => {
  test.skip(!isPhone(page, isMobile), 'phone only');
  await runHunt(page);
  await expect(page.locator('.saved-item')).toHaveCount(SAVED.length);
  const view = page.viewportSize()!;
  const list = page.locator('.saved-list');
  expect((await list.boundingBox())!.height).toBeLessThanOrEqual(view.height * 0.3 + 1);
  expect(await list.evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true);
  // The results header is fully on screen without scrolling the page.
  const header = await box(page, '.results-header');
  expect(header.y + header.height).toBeLessThanOrEqual(view.height);
});

test('phone: users row actions, fields and buttons are 44px', async ({ page, isMobile }) => {
  test.skip(!isPhone(page, isMobile), 'phone only');
  await page.goto('/admin/users');
  await page.locator('.users-table tbody tr').first().waitFor();
  await expectTargets(page, '.users-table tbody .actions-col button', 44);
  await expectTargets(page, '.users-table tbody .role-select', 44);
  await expectTargets(page, '.field-grid input, .field-grid select, .field-grid .btn-save', 44);

  // The new user fields take the full width of the card.
  const grid = await box(page, '.field-grid');
  const field = await box(page, '#new-username');
  expect(field.width).toBeGreaterThanOrEqual(grid.width - 1);
});

test.describe('phone login', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('phone: the login card fits at 360px with a 16px gutter', async ({ page, isMobile }) => {
    test.skip(!isPhone(page, isMobile), 'phone only');
    await page.setViewportSize({ width: 360, height: 780 });
    await page.goto('/login');
    const card = await box(page, '.login-card');
    expect(card.x).toBeGreaterThanOrEqual(16 - 1);
    expect(card.x + card.width).toBeLessThanOrEqual(360 - 16 + 1);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

// ── Phones and tablets ────────────────────────────────────────

test('rules: single buttons are 44px and the chip groups 32px', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'phone and tablet');
  await page.goto('/rules');
  await expectTargets(page, '.btn-new', 44);
  await page.locator('.btn-new').click();
  await page.locator('.editor-body').waitFor();
  await expectTargets(page, '.btn-add-cond, .editor-footer button', 44);
  await expectTargets(page, '.cond-del', 44, true);
  await expectTargets(page, '.logic-toggle button, .action-chip', 32);
});

test('hunting: the query and row buttons are 44px', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'phone and tablet');
  await runHunt(page);
  await expectTargets(page, '.query-actions button', 44);
  await expectTargets(page, '.saved-del', 44, true);
  await expectTargets(page, '.investigate-btn', 44, true);
});

test('settings: the card headers that open and close a card are 44px', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'phone and tablet');
  await page.goto('/settings');
  await expectTargets(page, '.card-summary', 44);
});

test('the console toggle is a named 44px touch target', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'phone and tablet');
  await page.goto('/settings');
  const toggle = page.getByRole('button', { name: 'Toggle console' });
  await expect(toggle).toBeVisible();
  const r = (await toggle.boundingBox())!;
  expect(r.width).toBeGreaterThanOrEqual(44);
  expect(r.height).toBeGreaterThanOrEqual(44);
});

// ── Desktop guard ─────────────────────────────────────────────

test.describe('desktop at 1025px', () => {
  test.skip(({ isMobile }) => !!isMobile, 'resizes a desktop browser');

  test('hunting keeps the 260px query column beside the results', async ({ page }) => {
    await page.setViewportSize({ width: 1025, height: 768 });
    await runHunt(page);
    const query = await box(page, '.hunt-sidebar');
    const results = await box(page, '.hunt-results');
    expect(Math.round(query.width)).toBe(260);
    expect(results.x).toBeGreaterThanOrEqual(query.x + query.width - 1);
    expect(Math.abs(results.y - query.y)).toBeLessThan(1);
    expect((await box(page, '.investigate-btn')).height).toBeLessThan(44);
  });

  test('the console toggle and the rules buttons keep their desktop size', async ({ page }) => {
    await page.setViewportSize({ width: 1025, height: 768 });
    await page.goto('/rules');
    expect((await box(page, '.console-toggle-btn')).height).toBeLessThan(44);
    expect((await box(page, '.btn-new')).height).toBeLessThan(44);
  });

  test.describe('signed out', () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test('the login card stays 360px with its desktop padding', async ({ page }) => {
      await page.setViewportSize({ width: 1025, height: 768 });
      await page.goto('/login');
      const card = page.locator('.login-card');
      expect(Math.round((await card.boundingBox())!.width)).toBe(360);
      expect(await card.evaluate(el => getComputedStyle(el).padding)).toBe('32px 36px 28px');
    });
  });
});
