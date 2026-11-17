import { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import type { DetectionRule } from '../src/app/shared/models/threat.models';

// Small fixes (PR 7): the rule toggle (hit area, on-dot contrast), the
// console input and the login demo hint. Every test starts logged in as the
// demo admin (see auth.setup.ts), except the login test.
//
// The rules tests stub only GET /api/rules: the demo server starts with none.

const RULES: DetectionRule[] = [1, 2, 3].map(i => ({
  id: `r${i}`, name: `Rule number ${i}`, enabled: i !== 2, logic: 'AND',
  conditions: [{ field: 'score', operator: '>', value: 70 + i }], actions: ['alert'],
  match_count: i * 3, created_at: '2026-11-16T10:00:00Z',
}) as DetectionRule);

async function openRules(page: Page) {
  await page.route(url => url.pathname === '/api/rules', route =>
    route.request().method() === 'GET'
      ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RULES) })
      : route.fallback());
  await page.goto('/rules');
  await expect(page.locator('.rule-item:not(.sk-rule-item)')).toHaveCount(RULES.length);
}

type Rect = { left: number; top: number; right: number; bottom: number };

/** The toggle's hit area (its box grown by the ::after insets) and its neighbours. */
const toggleGeometry = (page: Page, index: number) =>
  page.locator('.rule-item:not(.sk-rule-item)').nth(index).evaluate(item => {
    const rect = (el: Element): Rect => {
      const r = el.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
    };
    const toggle = item.querySelector('.rule-toggle')!;
    const after = getComputedStyle(toggle, '::after');
    const t = rect(toggle);
    const px = (v: string) => (v === 'auto' ? 0 : parseFloat(v));
    const hit = after.content === 'none' ? t : {
      left: t.left + px(after.left), top: t.top + px(after.top),
      right: t.right - px(after.right), bottom: t.bottom - px(after.bottom),
    };
    return {
      toggle: t, hit, item: rect(item), info: rect(item.querySelector('.rule-info')!),
      content: after.content,
    };
  });

const overlaps = (a: Rect, b: Rect) =>
  a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;

/** WCAG contrast of the on dot against the on track, both resolved over the
 *  first opaque background behind the row. */
const onDotContrast = (page: Page) => page.evaluate(() => {
  const toggle = document.querySelector('.rule-toggle.on')!;
  const dot = toggle.querySelector('.toggle-dot')!;
  let under: Element | null = toggle.closest('.rule-item');
  let base = 'rgba(0, 0, 0, 0)';
  while (under) {
    const bg = getComputedStyle(under).backgroundColor;
    if (bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') { base = bg; break; }
    under = under.parentElement;
  }
  if (!under) base = getComputedStyle(document.body).backgroundColor;
  const ctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!;
  const paint = (...colors: string[]) => {
    ctx.clearRect(0, 0, 1, 1);
    for (const c of colors) { ctx.fillStyle = c; ctx.fillRect(0, 0, 1, 1); }
    return [...ctx.getImageData(0, 0, 1, 1).data.slice(0, 3)];
  };
  const lum = (rgb: number[]) => {
    const [r, g, b] = rgb.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const track = paint(base, getComputedStyle(toggle).backgroundColor);
  const dotRgb = paint(base, getComputedStyle(toggle).backgroundColor, getComputedStyle(dot).backgroundColor);
  const [hi, lo] = [lum(track), lum(dotRgb)].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
});

// ── Phones and tablets ────────────────────────────────────────

test('rules: the toggle hit area is 44px and does not reach the rule name or the next row', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'phone and tablet');
  await openRules(page);
  const rows = await Promise.all(RULES.map((_, i) => toggleGeometry(page, i)));
  for (let i = 0; i < rows.length; i++) {
    const { toggle, hit, item, info } = rows[i];
    expect(Math.round(toggle.right - toggle.left)).toBe(28);      // the look is unchanged
    expect(Math.round(toggle.bottom - toggle.top)).toBe(16);
    expect(hit.right - hit.left).toBeGreaterThanOrEqual(44);
    expect(hit.bottom - hit.top).toBeGreaterThanOrEqual(44);
    expect(overlaps(hit, info)).toBe(false);
    for (let j = 0; j < rows.length; j++) {
      if (j !== i) expect(overlaps(hit, rows[j].item)).toBe(false);
    }
    expect(hit.top).toBeGreaterThanOrEqual(item.top - 0.5);
    expect(hit.bottom).toBeLessThanOrEqual(item.bottom + 0.5);
  }

  // A tap 6px above the visible toggle lands on the toggle.
  const first = rows[0].toggle;
  const target = await page.evaluate(([x, y]) =>
    !!document.elementFromPoint(x, y)?.closest('.rule-toggle'),
  [first.left + 14, first.top - 6]);
  expect(target).toBe(true);
});

test('the console command input is a 44px touch target with a name', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'phone and tablet');
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Toggle console' }).click();
  const input = page.getByRole('textbox', { name: 'Console command' });
  await expect(input).toBeVisible();
  expect((await input.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await expect(page.getByRole('button', { name: 'Close console' })).toBeVisible();
});

test.describe('signed out', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('login at 320px: the demo hint wraps whole instead of being cut', async ({ page, isMobile }) => {
    test.skip(!isMobile || page.viewportSize()!.width > 768, 'phone only');
    await page.setViewportSize({ width: 320, height: 700 });
    await page.goto('/login');
    const buttons = page.locator('.demo-btn');
    await expect(buttons.first()).toBeVisible();
    for (const b of await buttons.all()) {
      const hint = b.locator('.demo-hint');
      expect(await hint.evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(0);
      const h = (await hint.boundingBox())!;
      const r = (await b.boundingBox())!;
      expect(h.x).toBeGreaterThanOrEqual(r.x - 0.5);
      expect(h.x + h.width).toBeLessThanOrEqual(r.x + r.width + 0.5);
      expect(h.y + h.height).toBeLessThanOrEqual(r.y + r.height + 0.5);
    }
  });
});

// ── Every project ─────────────────────────────────────────────

test('rules: the on dot has at least 3:1 against the on track in both themes', async ({ page }) => {
  await openRules(page);
  for (const theme of ['dark', 'light']) {
    await page.evaluate(t => { document.documentElement.dataset['theme'] = t; }, theme);
    expect(await onDotContrast(page), theme).toBeGreaterThanOrEqual(3);
  }
});

// ── Desktop guard ─────────────────────────────────────────────

test.describe('desktop at 1025px', () => {
  test.skip(({ isMobile }) => !!isMobile, 'resizes a desktop browser');

  test('the toggle has no enlarged hit area and the console input keeps its size', async ({ page }) => {
    await page.setViewportSize({ width: 1025, height: 768 });
    await openRules(page);
    expect((await toggleGeometry(page, 0)).content).toBe('none');
    await page.locator('.console-toggle-btn').click();
    const input = page.locator('.console-input');
    await expect(input).toBeVisible();
    expect((await input.boundingBox())!.height).toBeLessThan(44);
  });

  test.describe('signed out', () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test('the login demo hint keeps one line with an ellipsis rule', async ({ page }) => {
      await page.setViewportSize({ width: 1025, height: 768 });
      await page.goto('/login');
      const hint = page.locator('.demo-hint').first();
      await expect(hint).toBeVisible();
      expect(await hint.evaluate(el => getComputedStyle(el).textOverflow)).toBe('ellipsis');
      expect(await page.locator('.demo-btn').first().evaluate(el => getComputedStyle(el).flexWrap)).toBe('nowrap');
    });
  });
});
