import { TestBed } from '@angular/core/testing';
import { HttpRequest, provideHttpClient } from '@angular/common/http';
import { signal } from '@angular/core';
import matrix from '../../../../../testing/permission-matrix.json';
import { DemoSimulatorService } from '../services/demo-simulator.service';
import { AuthService } from '../services/auth';
import { CurrentUser } from './permissions';
import { Incident } from '../../shared/models/threat.models';

/**
 * The shared RBAC permission matrix (testing/permission-matrix.json) run
 * through the client-side check that gates the demo simulator and mirrors
 * the UI. The backend runs the same file against the real API
 * (backend/tests/test_permission_matrix.py), so client and server cannot
 * silently diverge.
 */

type Case = (typeof matrix.cases)[number];

const PEOPLE: Record<string, { self: CurrentUser; other: string; third: string }> = {
  analyst: { self: { username: 'alice', display_name: 'Alice Chen', role: 'analyst' }, other: 'bob', third: 'admin' },
  admin:   { self: { username: 'admin', display_name: 'Sarah Kim', role: 'admin' },   other: 'bob', third: 'alice' },
};

function fill<T>(value: T, names: Record<string, string>): T {
  if (typeof value === 'string') {
    return Object.entries(names).reduce((s, [k, v]) => s.split(`{${k}}`).join(v), value as string) as T;
  }
  if (Array.isArray(value)) return value.map(v => fill(v, names)) as T;
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, fill(v, names)])) as T;
  }
  return value;
}

describe('permission matrix (shared with the backend)', () => {
  const user = signal<CurrentUser | null>(null);
  let sim: DemoSimulatorService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), { provide: AuthService, useValue: { currentUser: user } }],
    });
    sim = TestBed.inject(DemoSimulatorService);
  });

  it('covers both roles for every action', () => {
    const roles = new Map<string, Set<string>>();
    for (const c of matrix.cases) {
      const key = `${c.action}|${c.owner}`;
      roles.set(key, (roles.get(key) ?? new Set()).add(c.role));
    }
    for (const set of roles.values()) expect([...set].sort()).toEqual(['admin', 'analyst']);
  });

  it.each(matrix.cases.map((c: Case) => [`${c.role}: ${c.action}${c.owner ? ` [${c.owner}]` : ''}`, c]))(
    '%s',
    (_name, c) => {
      const people = PEOPLE[c.role];
      const owner = { self: people.self.username, other: people.other, none: null }[c.owner ?? 'none'] ?? null;
      user.set(people.self);
      sim.overlay('/api/incidents', [{
        id: 'INC-M001', title: 'm', severity: 'high', status: 'open', attack_type: 'SQLi',
        source_region: 'US', event_count: 1, assigned_to: owner, created_at: 'x', updated_at: 'x',
        mitre_tags: [], notes: [], completed_tasks: [],
      } as Incident]);
      const names = {
        self: people.self.username, other: people.other, third: people.third,
        incident: 'INC-M001', alert: 'ALT-1', rule: 'r1', hunt: 'h1', ip: '8.8.8.8',
      };
      const path = fill(c.path, names);
      const req = new HttpRequest(c.method as 'POST', path, fill(c.body, names));

      expect(sim.authorize(req, path).allowed).toBe(c.expect === 'allow');
    },
  );
});
