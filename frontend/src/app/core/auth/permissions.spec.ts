import {
  CurrentUser,
  DENY_REASONS,
  canAssign,
  canManageConfiguration,
  canManageUsers,
  canPatchIncident,
  canReassign,
  canTakeIncident,
  canWorkOnIncident,
  canOpenUserAdmin,
  canUpdateUser,
  canCreateUser,
  canDeleteUser,
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

  it('user management: admin only', () => {
    expect(canManageUsers(ADMIN).allowed).toBe(true);
    expect(canManageUsers(ALICE)).toEqual({ allowed: false, reason: DENY_REASONS.admin });
    expect(canManageUsers(null).allowed).toBe(false);
  });

  it('no user: everything denied', () => {
    for (const d of [
      canWorkOnIncident(null, inc(null)), canAssign(null, inc(null), 'x'), canTakeIncident(null, inc(null)),
      canReassign(null), canPatchIncident(null, inc(null), {}), canManageConfiguration(null),
    ]) {
      expect(d).toEqual({ allowed: false, reason: DENY_REASONS.notAuthenticated });
    }
  });

  describe('manager', () => {
    const MIRA: CurrentUser = { username: 'mira', display_name: 'Mira Cohen', role: 'manager' };

    it('works on and assigns any incident, like an admin', () => {
      expect(canWorkOnIncident(MIRA, inc('bob')).allowed).toBe(true);
      expect(canWorkOnIncident(MIRA, inc(null)).allowed).toBe(true);
      expect(canAssign(MIRA, inc('bob'), 'alice').allowed).toBe(true);
      expect(canAssign(MIRA, inc('alice'), null).allowed).toBe(true);
      expect(canReassign(MIRA).allowed).toBe(true);
    });

    it('does not manage configuration or users', () => {
      expect(canManageConfiguration(MIRA)).toEqual({ allowed: false, reason: DENY_REASONS.admin });
      expect(canManageUsers(MIRA)).toEqual({ allowed: false, reason: DENY_REASONS.admin });
    });

    it('may open the Users screen (analysts may not)', () => {
      expect(canOpenUserAdmin(MIRA).allowed).toBe(true);
      expect(canOpenUserAdmin(ADMIN).allowed).toBe(true);
      expect(canOpenUserAdmin(ALICE).allowed).toBe(false);
    });

    const BOB = { username: 'bob', role: 'analyst' as const };
    it.each([
      [BOB,                                           { password: 'x' }, true],
      [{ username: 'dana', role: 'manager' as const }, { password: 'x' }, false],   // another manager
      [{ username: 'admin', role: 'admin' as const },  { password: 'x' }, false],
      [BOB,                                           { password: 'x', role: 'manager' }, false],  // reset smuggling a role
      [BOB,                                           { role: 'manager' }, false],
      [undefined,                                     { password: 'x' }, false],   // unknown target
    ])('canUpdateUser(target %o, body %o) -> %s', (target, body, allowed) => {
      const d = canUpdateUser(MIRA, target, body);
      expect(d.allowed).toBe(allowed);
      if (!d.allowed) expect(d.reason).toBe(DENY_REASONS.managerResetOnly);
    });

    it('admins update anyone; analysts nobody', () => {
      expect(canUpdateUser(ADMIN, BOB, { role: 'manager' }).allowed).toBe(true);
      expect(canUpdateUser(ADMIN, { username: 'dana', role: 'manager' }, { role: 'analyst' }).allowed).toBe(true);
      expect(canUpdateUser(ADMIN, BOB, { password: 'x' }).allowed).toBe(true);
      expect(canUpdateUser(ADMIN, { username: 'admin', role: 'admin' }, { role: 'admin' }).allowed).toBe(true);   // unchanged
      expect(canUpdateUser(ALICE, BOB, { password: 'x' })).toEqual({ allowed: false, reason: DENY_REASONS.admin });
    });

    it('nobody resets their OWN password here (Settings asks for the current one)', () => {
      const own = { allowed: false, reason: DENY_REASONS.ownPasswordInSettings };
      expect(canUpdateUser(ADMIN, { username: 'admin', role: 'admin' }, { password: 'x' })).toEqual(own);
      expect(canUpdateUser(MIRA, { username: 'mira', role: 'manager' }, { password: 'x' })).toEqual(own);
    });
  });

  describe('exactly one admin', () => {
    const fixed = { allowed: false, reason: DENY_REASONS.adminRoleFixed };

    it('the admin role is never granted', () => {
      expect(canUpdateUser(ADMIN, { username: 'bob', role: 'analyst' }, { role: 'admin' })).toEqual(fixed);
      expect(canUpdateUser(ADMIN, { username: 'dana', role: 'manager' }, { role: 'admin', password: 'x' })).toEqual(fixed);
      expect(canCreateUser(ADMIN, { role: 'admin' })).toEqual(fixed);
      expect(canCreateUser(ADMIN, { role: 'manager' }).allowed).toBe(true);
    });

    it('the admin is never demoted or deleted', () => {
      expect(canUpdateUser(ADMIN, { username: 'admin', role: 'admin' }, { role: 'analyst' })).toEqual(fixed);
      expect(canDeleteUser(ADMIN, { role: 'admin' })).toEqual({ allowed: false, reason: DENY_REASONS.adminUndeletable });
      expect(canDeleteUser(ADMIN, { role: 'manager' }).allowed).toBe(true);
    });

    it('non-admins cannot create or delete anyone', () => {
      expect(canCreateUser(ALICE, { role: 'analyst' })).toEqual({ allowed: false, reason: DENY_REASONS.admin });
      expect(canDeleteUser(ALICE, { role: 'analyst' })).toEqual({ allowed: false, reason: DENY_REASONS.admin });
    });
  });
});
