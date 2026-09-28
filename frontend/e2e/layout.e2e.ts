import { Page } from '@playwright/test';
import { expect, test } from './fixtures';

// Every test starts logged in as the demo admin (see auth.setup.ts).

/**
 * Layout checks on a phone and on a desktop. The main guard: no page may
 * push content past the right edge of the screen. The only allowed
 * horizontal scrolling is inside an element marked `.h-scroll` (wide tables).
 */

const PAGES = ['dashboard', 'threats', 'alerts', 'incidents', 'map', 'rules', 'hunting', 'settings', 'admin/users'];

/** Visible elements in the page area that are cut by the screen edge. */
async function overflowing(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const describe = (e: Element) =>
      `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}${[...e.classList].map(c => '.' + c).join('')}`;
    const bad: string[] = [];
    for (const el of document.querySelectorAll('section.content *')) {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || (r.right <= width + 1 && r.left >= -1)) continue;
      // Entirely off screen = an off-canvas panel (e.g. a closed drawer), not cut content.
      if (r.left >= width - 1 || r.right <= 1) continue;
      const style = getComputedStyle(el);
      if (style.visibility === 'hidden' || style.display === 'none') continue;
      if (el.closest('.h-scroll')) continue;   // intentional horizontal scroller
      // Shapes inside an <svg> (e.g. the pannable map) are clipped by the svg
      // itself; the <svg> element is checked like any other element.
      if (el instanceof SVGElement && el.ownerSVGElement) continue;
      bad.push(`${describe(el)} [${Math.round(r.left)}..${Math.round(r.right)} of ${width}]`);
    }
    return bad.slice(0, 10);
  });
}

for (const path of PAGES) {
  test(`/${path}: nothing crosses the screen edge`, async ({ page }) => {
    await page.goto(`/${path}`);
    await page.waitForLoadState('networkidle');
    expect(await overflowing(page)).toEqual([]);
  });
}

// A detail drawer must fit the screen once opened (closed, it sits off screen,
// which the edge check ignores). Threats fill in within seconds from the live
// stream; alerts and incidents depend on slower rules, so they are not waited for here.
test('/threats: an opened detail drawer fits the screen', async ({ page }) => {
  await page.goto('/threats');
  const first = page.locator('tbody tr').first();
  await first.waitFor({ timeout: 20_000 });   // wait for streamed data
  await first.click();
  await page.waitForTimeout(400);             // slide-in animation
  expect(await overflowing(page)).toEqual([]);
});

test('/hunting: a full results table fits the screen', async ({ page }) => {
  await page.goto('/threats');
  await page.locator('tbody tr').first().waitFor({ timeout: 20_000 });   // events exist
  await page.goto('/hunting');
  await page.locator('button.btn-run').first().click();
  await page.locator('.results-table tbody tr').first().waitFor();
  expect(await overflowing(page)).toEqual([]);
});

test.describe('phone rules', () => {
  test.skip(({ isMobile }) => !isMobile, 'phone only');

  test('one pane at a time: the editor replaces the list, and back returns', async ({ page }) => {
    await page.goto('/rules');
    const list = page.locator('.rules-sidebar');
    const editor = page.locator('.rules-editor');
    await expect(list).toBeVisible();
    await expect(editor).toBeHidden();

    await page.getByRole('button', { name: '+ New' }).click();
    await expect(editor).toBeVisible();
    await expect(list).toBeHidden();
    expect(await overflowing(page)).toEqual([]);

    await page.getByRole('button', { name: '← All rules' }).click();
    await expect(list).toBeVisible();
    await expect(editor).toBeHidden();
  });
});

test.describe('phone menu', () => {
  test.skip(({ isMobile }) => !isMobile, 'phone only');

  test('the sidebar is hidden until the menu button opens it', async ({ page }) => {
    await page.goto('/dashboard');
    const sidebar = page.locator('#app-sidebar');
    const toggle = page.getByRole('button', { name: 'Open menu' });

    await expect(sidebar).toBeHidden();
    await toggle.click();
    await expect(sidebar).toBeVisible();
    await expect(page.getByRole('button', { name: 'Close menu' })).toHaveAttribute('aria-expanded', 'true');
  });

  test('choosing a page closes the menu', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByRole('button', { name: 'Open menu' }).click();
    await page.getByRole('link', { name: 'Incidents' }).click();
    await page.waitForURL(/incidents/);
    await expect(page.locator('#app-sidebar')).toBeHidden();
  });

  test('Escape and the backdrop close the menu', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByRole('button', { name: 'Open menu' }).click();
    await page.keyboard.press('Escape');
    await expect(page.locator('#app-sidebar')).toBeHidden();

    await page.getByRole('button', { name: 'Open menu' }).click();
    await page.locator('.nav-backdrop').click({ position: { x: 350, y: 400 } });
    await expect(page.locator('#app-sidebar')).toBeHidden();
  });
});

test.describe('phone logout', () => {
  test.skip(({ isMobile }) => !isMobile, 'phone only');
  // Logout ends the session on the server, so this test must not use the
  // session shared by every other test: it logs in on its own first.
  test.use({ storageState: { cookies: [], origins: [] } });

  test('logout is reachable from the menu and ends the session', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: /Try as Admin/ }).click();
    await page.waitForURL(/dashboard/);
    await page.getByRole('button', { name: 'Open menu' }).click();
    await page.getByRole('button', { name: 'Log out' }).click();
    await page.waitForURL(/login/);
    expect(await page.evaluate(async () => (await fetch('/auth/me')).status)).toBe(401);
  });
});

test.describe('desktop', () => {
  test.skip(({ isMobile }) => !!isMobile, 'desktop only');

  test('the sidebar is always visible and there is no menu button', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('#app-sidebar')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open menu' })).toBeHidden();
  });
});
