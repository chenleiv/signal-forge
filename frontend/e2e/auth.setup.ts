import { test as setup } from './fixtures';

// Log in once (login is rate limited per IP) and share the session with
// every test through storageState.
export const ADMIN_STATE = 'e2e/.auth/admin.json';

setup('log in as the demo admin', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: /Try as Admin/ }).click();
  await page.waitForURL(/dashboard/);
  await page.context().storageState({ path: ADMIN_STATE });
});
