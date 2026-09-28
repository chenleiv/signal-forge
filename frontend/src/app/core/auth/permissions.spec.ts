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

// Who may do what, per role, is the shared permission matrix
// (permissions.matrix.spec.ts). These are the edges it does not reach:
// server wording, no-ops, smuggled fields, and helpers used only by the UI.
describe('permissions (mirror of backend/authz.py)', () => {
  describe('canWorkOnIncident', () => {
    it('uses the server wording for the reason', () => {
      expect(canWorkOnIncident(ALICE, inc('bob'))).toEqual({ allowed: false, reason: DENY_REASONS.work });
    });
  });

  describe('canAssign', () => {
    it.each([['bob'], [null]])('an unchanged assignee (%s) is a no-op, allowed even for an analyst', owner => {
      expect(canAssign(ALICE, inc(owner), owner).allowed).toBe(true);
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

  it('no user: everything denied', () => {
    for (const d of [
      canWorkOnIncident(null, inc(null)), canAssign(null, inc(null), 'x'), canTakeIncident(null, inc(null)),
      canReassign(null), canPatchIncident(null, inc(null), {}), canManageConfiguration(null),
      canManageUsers(null),
    ]) {
      expect(d).toEqual({ allowed: false, reason: DENY_REASONS.notAuthenticated });
    }
  });

  describe('manager', () => {
    const MIRA: CurrentUser = { username: 'mira', display_name: 'Mira Cohen', role: 'manager' };

    it('gets the assign dropdown, like an admin', () => {
      expect(canReassign(MIRA).allowed).toBe(true);
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
