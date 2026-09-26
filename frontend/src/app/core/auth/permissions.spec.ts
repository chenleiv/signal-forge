import {
  CurrentUser,
  DENY_REASONS,
  canAssign,
  canManageConfiguration,
  canPatchIncident,
  canReassign,
  canTakeIncident,
  canWorkOnIncident,
} from './permissions';

const ALICE: CurrentUser = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' };
const ADMIN: CurrentUser = { username: 'admin', display_name: 'Sarah Kim', role: 'admin' };
const inc = (assigned_to: string | null) => ({ assigned_to });

describe('permissions (mirror of backend/authz.py)', () => {
  describe('canWorkOnIncident', () => {
    it.each([
      ['own', 'alice', true],
      ["someone else's", 'bob', false],
      ['unassigned', null, false],
    ])('analyst on %s incident -> %s', (_label, owner, allowed) => {
      expect(canWorkOnIncident(ALICE, inc(owner as string | null)).allowed).toBe(allowed);
    });

    it.each(['alice', 'bob', null])('admin on incident owned by %s -> allowed', owner => {
      expect(canWorkOnIncident(ADMIN, inc(owner)).allowed).toBe(true);
    });

    it('uses the server wording for the reason', () => {
      expect(canWorkOnIncident(ALICE, inc('bob'))).toEqual({ allowed: false, reason: DENY_REASONS.work });
    });
  });

  describe('canAssign', () => {
    it.each([
      // owner,  new,     analyst, admin
      [null,     'alice', true,    true],   // take unassigned for self
      [null,     'bob',   false,   true],   // assign unassigned to someone else
      ['bob',    'alice', false,   true],   // take someone else's
      ['alice',  'bob',   false,   true],   // hand own away
      ['alice',  null,    false,   true],   // unassign own
      ['bob',    null,    false,   true],   // unassign someone else's
      ['bob',    'bob',   true,    true],   // unchanged: no-op
      [null,     null,    true,    true],   // unchanged: no-op
    ])('%s -> %s: analyst %s, admin %s', (owner, next, analyst, admin) => {
      expect(canAssign(ALICE, inc(owner as string | null), next as string | null).allowed).toBe(analyst);
      expect(canAssign(ADMIN, inc(owner as string | null), next as string | null).allowed).toBe(admin);
    });
  });

  describe('canTakeIncident / canReassign', () => {
    it('take: only unassigned incidents, for any role', () => {
      expect(canTakeIncident(ALICE, inc(null)).allowed).toBe(true);
      expect(canTakeIncident(ADMIN, inc(null)).allowed).toBe(true);
      expect(canTakeIncident(ALICE, inc('bob')).allowed).toBe(false);
      expect(canTakeIncident(ALICE, inc('alice')).allowed).toBe(false);
    });

    it('reassign (the dropdown): admin only', () => {
      expect(canReassign(ADMIN).allowed).toBe(true);
      expect(canReassign(ALICE)).toEqual({ allowed: false, reason: DENY_REASONS.assign });
    });
  });

  describe('canPatchIncident (every field vs CURRENT state)', () => {
    it('an unchanged assignee does not smuggle a status change', () => {
      expect(canPatchIncident(ALICE, inc('bob'), { assigned_to: 'bob', status: 'closed' }).allowed).toBe(false);
    });

    it('the owner cannot hand the incident away along with a status change', () => {
      expect(canPatchIncident(ALICE, inc('alice'), { status: 'closed', assigned_to: 'bob' }).allowed).toBe(false);
    });

    it('take + status in one request is denied (not yet the assignee)', () => {
      expect(canPatchIncident(ALICE, inc(null), { assigned_to: 'alice', status: 'closed' }).allowed).toBe(false);
    });

    it('allowed combinations', () => {
      expect(canPatchIncident(ALICE, inc('alice'), { status: 'closed' }).allowed).toBe(true);
      expect(canPatchIncident(ALICE, inc(null), { assigned_to: 'alice' }).allowed).toBe(true);
      expect(canPatchIncident(ADMIN, inc('bob'), { status: 'closed', assigned_to: null }).allowed).toBe(true);
    });
  });

  it('configuration (rules, behavioral settings): admin only', () => {
    expect(canManageConfiguration(ADMIN).allowed).toBe(true);
    expect(canManageConfiguration(ALICE)).toEqual({ allowed: false, reason: DENY_REASONS.admin });
  });

  it('no user: everything denied', () => {
    for (const d of [
      canWorkOnIncident(null, inc(null)), canAssign(null, inc(null), 'x'), canTakeIncident(null, inc(null)),
      canReassign(null), canPatchIncident(null, inc(null), {}), canManageConfiguration(null),
    ]) {
      expect(d).toEqual({ allowed: false, reason: DENY_REASONS.notAuthenticated });
    }
  });
});
