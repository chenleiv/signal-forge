import { expect, test, type Locator, type Page } from '@playwright/test';
import type { ThreatStats } from '../src/app/shared/models/threat.models';

// Settings (PR 7b): every card starts closed, Save Settings is enabled only
// when the form differs from the stored settings, and a disabled .btn-save
// (Save Settings or Change password) looks disabled: a transparent
// background, a $border border and $muted text.
//
// The phone and desktop pass already sits at about 59 of the 60 ws-tickets
// per minute the server allows per IP, and every signed-in page also polls
// /api/stats (50 per minute per IP). So this spec stubs GET /api/stats and
// aborts GET /auth/ws-ticket (the page then shows "reconnecting", which the
// Settings checks do not depend on). One test, so one page load per project.

const STATS: ThreatStats = {
  severity_counts: { critical: 0, high: 0, medium: 0, low: 0 },
  attack_types: {},
  events_per_min: [],
  top_ips: [],
};

async function stubStats(page: Page) {
  await page.route(url => url.pathname === '/api/stats', route =>
    route.request().method() === 'GET'
      ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STATS) })
      : route.fallback());
}

/** No ticket request reaches the server, so this spec uses none of its ticket limit. */
async function blockWsTicket(page: Page) {
  await page.route(url => url.pathname === '/auth/ws-ticket', route =>
    route.request().method() === 'GET' ? route.abort() : route.fallback());
}

/** The computed look of a button, next to the theme tokens it should use. */
async function look(button: Locator) {
  return button.evaluate(el => {
    const probe = document.createElement('span');
    probe.style.color = 'var(--c-muted)';
    probe.style.borderColor = 'var(--c-border)';
    document.body.appendChild(probe);
    const tokens = getComputedStyle(probe);
    const s = getComputedStyle(el);
    const result = {
      background: s.backgroundColor, color: s.color, border: s.borderTopColor, borderWidth: s.borderTopWidth,
      muted: tokens.color, borderToken: tokens.borderTopColor,
    };
    probe.remove();
    return result;
  });
}

function expectDisabledLook(l: Awaited<ReturnType<typeof look>>) {
  expect(l.background).toBe('rgba(0, 0, 0, 0)');
  expect(l.color).toBe(l.muted);
  expect(l.border).toBe(l.borderToken);
  expect(l.borderWidth).toBe('1px');
}

test('settings: cards start closed, Save is enabled only with changes, and disabled buttons look disabled',
  async ({ page }) => {
    await stubStats(page);
    await blockWsTicket(page);
    await page.goto('/settings');

    const details = page.locator('section.card details.card-details');
    await expect(details).toHaveCount(5);
    for (const d of await details.all()) expect(await d.evaluate(el => (el as HTMLDetailsElement).open)).toBe(false);

    const save = page.locator('.actions .btn-save');
    await expect(save).toBeDisabled();
    const sizeBefore = (await save.boundingBox())!;
    expectDisabledLook(await look(save));

    // The password button keeps its own rule (disabled while the form is incomplete; locked in the demo).
    await page.locator('summary.card-summary', { hasText: 'Change Password' }).click();
    const pwButton = page.locator('.pw-details .btn-save');
    await expect(pwButton).toBeDisabled();
    expectDisabledLook(await look(pwButton));

    await page.locator('summary.card-summary', { hasText: 'Connection' }).click();
    const buffer = page.locator('#buffer-size');
    const original = await buffer.inputValue();
    await buffer.fill('250');
    await expect(save).toBeEnabled();
    const sizeAfter = (await save.boundingBox())!;
    expect(sizeAfter.height).toBeCloseTo(sizeBefore.height, 0);   // the border does not change the size

    await buffer.fill(original);
    await expect(save).toBeDisabled();

    await buffer.fill('250');
    await save.click();
    await expect(save).toHaveText(/Saved/);
    await expect(save).toBeDisabled();
    await expect(save).toHaveText(/Save Settings/, { timeout: 5000 });
    await expect(save).toBeDisabled();
  });
