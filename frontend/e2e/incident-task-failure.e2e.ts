import { expect, test } from './fixtures';
import type { Incident, ThreatStats } from '../src/app/shared/models/threat.models';

// A failed response task update shows a message and puts the checkbox back.
//
// Same setup as incident-update-failure.e2e.ts: the test server runs in demo
// mode, so this test reports demo mode as off to the client, serves one
// incident, and fails its task PATCH with a 403 from the stub. Nothing is
// written on the server. It also stubs GET /api/stats and aborts GET
// /auth/ws-ticket, so it uses none of the per-IP limits of the e2e server
// (see docs/DECISIONS.md, "E2E: one pass per project").

const STATS: ThreatStats = {
  severity_counts: { critical: 0, high: 0, medium: 0, low: 0 },
  attack_types: {},
  events_per_min: [],
  top_ips: [],
};
const now = new Date().toISOString();
const INCIDENT: Incident = {
  id: 'INC-3002', title: 'Brute force against the VPN', severity: 'high',
  status: 'open', attack_type: 'BruteForce', source_ip: '185.220.101.35',
  source_region: 'RU', event_count: 8, assigned_to: 'admin',
  created_at: now, updated_at: now, mitre_tags: [], notes: [], completed_tasks: [],
};
const REASON = 'Only the assignee, a manager or an admin can change this incident';

test('a failed task update shows the reason and unchecks the task', async ({ page }) => {
  const json = (status: number, body: unknown) =>
    ({ status, contentType: 'application/json', body: JSON.stringify(body) });
  await page.route(url => url.pathname === '/api/stats', route =>
    route.request().method() === 'GET' ? route.fulfill(json(200, STATS)) : route.fallback());
  await page.route(url => url.pathname === '/auth/ws-ticket', route =>
    route.request().method() === 'GET' ? route.abort() : route.fallback());
  await page.route(url => url.pathname === '/api/config', route =>
    route.request().method() === 'GET' ? route.fulfill(json(200, { demo_mode: false })) : route.fallback());
  await page.route(url => url.pathname === '/api/incidents', route =>
    route.request().method() === 'GET' ? route.fulfill(json(200, [INCIDENT])) : route.fallback());
  await page.route(url => url.pathname === `/api/incidents/${INCIDENT.id}/tasks`, route =>
    route.request().method() === 'PATCH' ? route.fulfill(json(403, { detail: REASON })) : route.fallback());

  await page.goto('/incidents');
  await page.locator('.inc-row', { hasText: INCIDENT.id }).click();

  const task = page.locator('.task-item').first();
  await expect(task).toHaveAttribute('aria-checked', 'false');

  const patch = page.waitForRequest(r => r.method() === 'PATCH' && r.url().endsWith(`/api/incidents/${INCIDENT.id}/tasks`));
  await task.click();
  await patch;

  await expect(page.locator('.toast')).toHaveText(`Could not update ${INCIDENT.id}: ${REASON}`);
  await expect(task).toHaveAttribute('aria-checked', 'false');
  await expect(page.getByText('RESPONSE TASKS (0/5)')).toBeVisible();
});
