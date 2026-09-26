import { TestBed } from '@angular/core/testing';
import { HttpRequest, provideHttpClient } from '@angular/common/http';
import { signal } from '@angular/core';
import { DemoSimulatorService } from './demo-simulator.service';
import { AuthService } from './auth';
import { CurrentUser, DENY_REASONS } from '../auth/permissions';
import { Incident } from '../../shared/models/threat.models';

const ALICE: CurrentUser = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' };
const ADMIN: CurrentUser = { username: 'admin', display_name: 'Sarah Kim', role: 'admin' };

function incident(id: string, assigned_to: string | null): Incident {
  return {
    id, title: 't', severity: 'high', status: 'open', attack_type: 'SQLi',
    source_region: 'US', event_count: 1, assigned_to, created_at: 'x', updated_at: 'x',
    mitre_tags: [], notes: [], completed_tasks: [],
  } as Incident;
}

describe('DemoSimulatorService', () => {
  let sim: DemoSimulatorService;
  const user = signal<CurrentUser | null>(ALICE);

  beforeEach(() => {
    user.set(ALICE);
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), { provide: AuthService, useValue: { currentUser: user } }],
    });
    sim = TestBed.inject(DemoSimulatorService);
    sim.overlay('/api/incidents', [incident('INC-1', 'bob'), incident('INC-2', 'alice'), incident('INC-3', null)]);
  });

  const req = (method: string, url: string, body: unknown = {}) =>
    new HttpRequest(method as 'PATCH', url, body);

  describe('authorize (same matrix as the server)', () => {
    it('denies an analyst working on someone else\'s incident', () => {
      for (const r of [
        req('PATCH', '/api/incidents/INC-1', { status: 'closed' }),
        req('POST', '/api/incidents/INC-1/notes', { text: 'x' }),
        req('PATCH', '/api/incidents/INC-1/tasks', { completed_tasks: [0] }),
      ]) {
        expect(sim.authorize(r, r.url)).toEqual({ allowed: false, reason: DENY_REASONS.work });
      }
    });

    it('allows an analyst on their own incident, and taking an unassigned one', () => {
      expect(sim.authorize(req('PATCH', '/api/incidents/INC-2', { status: 'closed' }), '/api/incidents/INC-2').allowed).toBe(true);
      expect(sim.authorize(req('PATCH', '/api/incidents/INC-3', { assigned_to: 'alice' }), '/api/incidents/INC-3').allowed).toBe(true);
    });

    it('denies an analyst assigning to someone else', () => {
      const r = req('PATCH', '/api/incidents/INC-3', { assigned_to: 'bob' });
      expect(sim.authorize(r, r.url)).toEqual({ allowed: false, reason: DENY_REASONS.assign });
    });

    it('denies rule and behavioral changes to analysts, allows them to admins', () => {
      const writes = [
        req('POST', '/api/rules', { name: 'r' }),
        req('PATCH', '/api/rules/r1', { enabled: false }),
        req('DELETE', '/api/rules/r1'),
        req('PATCH', '/api/behavioral/settings', { cooldown_min: 5 }),
      ];
      for (const r of writes) expect(sim.authorize(r, r.url)).toEqual({ allowed: false, reason: DENY_REASONS.admin });
      user.set(ADMIN);
      for (const r of writes) expect(sim.authorize(r, r.url).allowed).toBe(true);
    });

    it('allows shared actions to everyone', () => {
      for (const r of [
        req('PATCH', '/api/alerts/a1', { status: 'acknowledged' }),
        req('POST', '/api/ip/8.8.8.8/block'),
        req('POST', '/api/incidents/from-ip', { ip: '8.8.8.8' }),
      ]) {
        expect(sim.authorize(r, r.url).allowed).toBe(true);
      }
    });

    it('checks against the locally simulated state, not a stale server copy', () => {
      // alice takes INC-3 locally; she may now work on it.
      sim.simulate(req('PATCH', '/api/incidents/INC-3', { assigned_to: 'alice' }), '/api/incidents/INC-3');
      expect(sim.authorize(req('PATCH', '/api/incidents/INC-3', { status: 'closed' }), '/api/incidents/INC-3').allowed).toBe(true);
    });
  });

  it('assigns a simulated new case to its creator', () => {
    const res = sim.simulate(req('POST', '/api/incidents/from-ip', { ip: '8.8.8.8' }), '/api/incidents/from-ip');
    expect((res!.body as Incident).assigned_to).toBe('alice');
  });

  it('writes simulated notes as the logged-in user', () => {
    const res = sim.simulate(req('POST', '/api/incidents/INC-2/notes', { text: 'hi' }), '/api/incidents/INC-2/notes');
    expect((res!.body as { author: string }).author).toBe('alice');
  });

  it('keeps an acknowledged alert acknowledged after the list is refetched', () => {
    const serverAlerts = [{ id: 'a1', status: 'new' }];

    sim.overlay('/api/alerts', serverAlerts);

    // The user acknowledges the alert.
    const req = new HttpRequest('PATCH', '/api/alerts/a1', { status: 'acknowledged' });
    sim.simulate(req, '/api/alerts/a1');

    const result = sim.overlay('/api/alerts', serverAlerts) as { status: string }[];

    // The refetched list must keep the local acknowledgement.
    expect(result[0].status).toBe('acknowledged');
  });
});
