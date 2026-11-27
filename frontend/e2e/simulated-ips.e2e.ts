import { expect, test } from './fixtures';

// Demo mode shows simulated IP addresses only (docs/DECISIONS.md): every IP
// is in a documentation range, and a visible "Simulated" tag with a name for
// screen readers sits next to the data. Runs on the real demo server (serve.mjs).

const POOL_IP = /^(192\.0\.2|198\.51\.100|203\.0\.113)\.\d{1,3}$/;
const TAG_NAME = 'Simulated data: these IP addresses are not real hosts';

test('dashboard: the stream and top IPs carry a named "Simulated" tag', async ({ page }) => {
  await page.goto('/dashboard');
  const tags = page.getByRole('note', { name: TAG_NAME });
  await expect(tags).toHaveCount(2);
  for (const tag of await tags.all()) {
    await expect(tag).toBeVisible();
    await expect(tag).toHaveText('Simulated');
  }
});

test('threats: every listed IP is simulated, and the table and drawer are tagged', async ({ page }) => {
  await page.goto('/threats');
  const rows = page.locator('tr.ip-row');
  await rows.first().waitFor({ timeout: 20_000 });   // wait for streamed data

  for (const ip of await page.locator('tr.ip-row .cell-ip').allTextContents()) {
    expect(ip.trim()).toMatch(POOL_IP);
  }
  await expect(page.locator('.table-header').getByRole('note', { name: TAG_NAME })).toBeVisible();

  await rows.first().click();
  const drawer = page.locator('app-threat-detail-drawer');
  await expect(drawer.locator('.drawer-ip')).toHaveText(POOL_IP);
  const tag = drawer.getByRole('note', { name: TAG_NAME });
  await expect(tag).toBeVisible();
  await expect(tag).toHaveText('Simulated');
});

test('a lookup of an IP outside the simulated feed is refused', async ({ page }) => {
  await page.goto('/dashboard');
  const status = await page.evaluate(async () => (await fetch('/api/ip/8.8.8.8/geo')).status);
  expect(status).toBe(404);
});
