import { expect, test } from './fixtures';

// The icons come from the real server (FastAPI serving the production build,
// e2e/serve.mjs) as images, never as the SPA's index.html, for GET and HEAD.
// A missing icon is 404, while client-side routes still get the SPA.
// Backend side: backend/tests/test_favicon.py; file format: scripts/check-icons.mjs.
//
// Rate limits: none of these paths is rate limited.

const ICONS = [
  { path: '/favicon.ico', type: 'image/x-icon', magic: [0x00, 0x00, 0x01, 0x00] },
  { path: '/favicon.svg', type: 'image/svg+xml', magic: [0x3c, 0x73, 0x76, 0x67] },  // "<svg"
  { path: '/apple-touch-icon.png', type: 'image/png', magic: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a] },
];

for (const { path, type, magic } of ICONS) {
  test(`${path} is served as ${type}, not the SPA`, async ({ request }) => {
    const get = await request.get(path);
    expect(get.status()).toBe(200);
    expect(get.headers()['content-type']).toBe(type);
    expect(get.headers()['x-content-type-options']).toBe('nosniff');
    const body = await get.body();
    expect([...body.subarray(0, magic.length)]).toEqual(magic);
    expect(body.toString('latin1').toLowerCase()).not.toContain('<html');

    const head = await request.head(path);
    expect(head.status()).toBe(200);
    expect(head.headers()['content-type']).toBe(type);
  });
}

test('a missing icon is 404 and a deep route still gets the SPA', async ({ request }) => {
  const missing = await request.get('/apple-touch-icon-precomposed.png');
  expect(missing.status()).toBe(404);
  expect(missing.headers()['content-type'] ?? '').not.toContain('text/html');

  const route = await request.get('/incidents/INC-1/deep/route');
  expect(route.status()).toBe(200);
  expect(route.headers()['content-type']).toContain('text/html');
  expect(await route.text()).toContain('<app-root>');
});

test('the page links the icons', async ({ page }) => {
  await page.goto('/');
  const head = page.locator('head');
  await expect(head.locator('link[rel="icon"][href="favicon.ico"]')).toHaveCount(1);
  await expect(head.locator('link[rel="icon"][type="image/svg+xml"][href="favicon.svg"]')).toHaveCount(1);
  await expect(head.locator('link[rel="apple-touch-icon"][href="apple-touch-icon.png"]')).toHaveCount(1);
});
