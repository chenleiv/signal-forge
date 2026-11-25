import { Page } from '@playwright/test';
import { expect, test } from './fixtures';

// The export menu has four items (CSV, PDF, JSON, Markdown). On every project
// viewport, and at 360px on phones, each item must be fully inside the
// viewport, not clipped by an ancestor with overflow: hidden and not covered
// by another element (the element at its centre is the item itself), and the
// open menu must not make the page scroll sideways.
// Every test starts logged in as the demo admin (see auth.setup.ts).

const PAGES = [
  { name: 'threat table', path: '/threats', host: 'app-threat-table app-export-menu' },
  { name: 'incidents', path: '/incidents', host: 'app-incidents app-export-menu' },
];

async function openMenu(page: Page, path: string, host: string) {
  await page.goto(path);
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

for (const p of PAGES) {
  test(`export menu: all four items stay inside the viewport on the ${p.name}`, async ({ page }) => {
    await openMenu(page, p.path, p.host);
    await expectItemsVisible(page, p.host);
  });

  test(`phone: export menu fits at 360px on the ${p.name}`, async ({ page, isMobile }) => {
    test.skip(!(isMobile && page.viewportSize()!.width <= 768), 'phone only');
    await page.setViewportSize({ width: 360, height: 780 });
    await openMenu(page, p.path, p.host);
    await expectItemsVisible(page, p.host);
  });
}
