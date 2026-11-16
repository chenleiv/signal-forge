import { expect, test } from './fixtures';

// Shell behaviour around the breakpoints: $narrow (768px) and $tablet (1024px).
// Every test starts logged in as the demo admin (see auth.setup.ts).

test.describe('tablet breakpoint', () => {
  test.skip(({ isMobile }) => !!isMobile, 'resizes a desktop browser');

  test('the menu replaces the sidebar at 1024px and the sidebar returns at 1025px', async ({ page }) => {
    const sidebar = page.locator('#app-sidebar');
    const toggle = page.getByRole('button', { name: 'Open menu' });

    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto('/dashboard');
    await expect(sidebar).toBeHidden();
    await expect(toggle).toBeVisible();

    await page.setViewportSize({ width: 1025, height: 768 });
    await expect(sidebar).toBeVisible();
    await expect(toggle).toBeHidden();
  });

  test('at tablet width the open menu works from the keyboard', async ({ page }) => {
    await page.setViewportSize({ width: 820, height: 1180 });
    await page.goto('/dashboard');
    const toggle = page.getByRole('button', { name: 'Open menu' });
    await toggle.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#app-sidebar')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#app-sidebar')).toBeHidden();
  });
});

test('the console fits the screen and leaves most of a phone screen free', async ({ page, isMobile }) => {
  await page.goto('/dashboard');
  await page.locator('.console-toggle-btn').click();
  await page.waitForTimeout(300);                    // slide-up animation (0.2s)
  const box = (await page.locator('.console').boundingBox())!;
  const view = page.viewportSize()!;
  expect(box.x).toBeGreaterThanOrEqual(-1);
  expect(box.x + box.width).toBeLessThanOrEqual(view.width + 1);
  expect(box.y + box.height).toBeLessThanOrEqual(view.height + 1);
  if (isMobile && view.width <= 768) {
    expect(box.height).toBeLessThanOrEqual(view.height * 0.4 + 1);
  }
});

test('an opened detail drawer leaves the page visible on a tablet', async ({ page, isMobile }) => {
  const view = page.viewportSize()!;
  test.skip(!isMobile || view.width <= 768 || view.width > 1024, 'tablet only');
  await page.goto('/threats');
  const first = page.locator('tr.ip-row').first();   // a data row, not a loading placeholder
  await first.waitFor({ timeout: 20_000 });          // wait for streamed data
  await first.click();
  await page.waitForTimeout(400);                    // slide-in animation
  const box = (await page.locator('.drawer-overlay.open').boundingBox())!;
  expect(box.width).toBeLessThanOrEqual(view.width * 0.9 + 1);
});
