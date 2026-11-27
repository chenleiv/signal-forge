import { expect, test } from './fixtures';
import type { Incident } from '../src/app/shared/models/threat.models';

// A failed incident update shows a message and leaves the old value on screen.
//
// The test server runs in demo mode, where the browser simulates incident
// writes and never sends them. So this test reports demo mode as off to the
// client (GET /api/config), serves one incident, and fails its PATCH with a
// 409 from the stub. Nothing is written on the server.

const now = new Date().toISOString();
const INCIDENT: Incident = {
  id: 'INC-3001', title: 'Port scan against the DMZ', severity: 'high',
  status: 'open', attack_type: 'PortScan', source_ip: '203.0.113.34',
  source_region: 'RU', event_count: 12, assigned_to: 'admin',
  created_at: now, updated_at: now, mitre_tags: [], notes: [], completed_tasks: [],
};
const REASON = 'The assignee changed; reload and try again';

test('a failed assignee change shows the reason and puts the old assignee back', async ({ page }) => {
  const json = (status: number, body: unknown) =>
    ({ status, contentType: 'application/json', body: JSON.stringify(body) });
  await page.route(url => url.pathname === '/api/config', route =>
    route.request().method() === 'GET' ? route.fulfill(json(200, { demo_mode: false })) : route.fallback());
  await page.route(url => url.pathname === '/api/incidents', route =>
    route.request().method() === 'GET' ? route.fulfill(json(200, [INCIDENT])) : route.fallback());
  await page.route(url => url.pathname === `/api/incidents/${INCIDENT.id}`, route =>
    route.request().method() === 'PATCH' ? route.fulfill(json(409, { detail: REASON })) : route.fallback());

  await page.goto('/incidents');
  await page.locator('.inc-row', { hasText: INCIDENT.id }).click();

  const select = page.locator('.assignee-select');
  await expect(select).toHaveValue('admin');

  const patch = page.waitForRequest(r => r.method() === 'PATCH' && r.url().endsWith(`/api/incidents/${INCIDENT.id}`));
  await select.selectOption('analyst');
  await patch;

  await expect(page.locator('.toast')).toHaveText(`Could not update ${INCIDENT.id}: ${REASON}`);
  await expect(select).toHaveValue('admin');
  await expect(page.locator('.inc-row', { hasText: INCIDENT.id })).toContainText('admin');
});
