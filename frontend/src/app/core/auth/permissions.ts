import { Incident, UserRole, UserSummary } from '../../shared/models/threat.models';

/**
 * Client-side mirror of backend/authz.py, used by the UI and the demo
 * simulator. Reasons are the server's exact messages. UX only: the server
 * re-checks everything.
 */

export type CurrentUser = UserSummary;

export type Decision = { allowed: true } | { allowed: false; reason: string };

export const DENY_REASONS = {
  notAuthenticated: 'Not authenticated',
  work: 'Only the assignee, a manager or an admin can change this incident',
  assign: 'Analysts can only take unassigned incidents for themselves',
  admin: 'Admin role required',
  managerResetOnly: "Managers can only reset analysts' passwords",
  adminRoleFixed: 'There is exactly one admin: the admin role cannot be granted or removed',
  adminUndeletable: 'The admin account cannot be deleted',
  ownPasswordInSettings: 'Change your own password in Settings (it asks for your current password)',
} as const;

/** Roles that work on and assign any incident (backend: INCIDENT_LEADS). */
const INCIDENT_LEADS: readonly UserRole[] = ['admin', 'manager'];
const isLead = (user: CurrentUser) => INCIDENT_LEADS.includes(user.role);

const ALLOW: Decision = { allowed: true };
const deny = (reason: string): Decision => ({ allowed: false, reason });

type IncidentRef = Pick<Incident, 'assigned_to'>;

/** Status, notes and tasks: the assignee, a manager or an admin. */
export function canWorkOnIncident(user: CurrentUser | null, incident: IncidentRef): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  if (isLead(user) || incident.assigned_to === user.username) return ALLOW;
  return deny(DENY_REASONS.work);
}

/**
 * Admins assign anyone (or no one). Analysts only take an unassigned incident
 * for themselves. An unchanged assignee is a no-op and always allowed.
 */
export function canAssign(
  user: CurrentUser | null,
  incident: IncidentRef,
  newAssignee: string | null,
): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  if (newAssignee === incident.assigned_to) return ALLOW;
  if (isLead(user)) return ALLOW;
  if (incident.assigned_to === null && newAssignee === user.username) return ALLOW;
  return deny(DENY_REASONS.assign);
}

/** The "Take case" action: an unassigned incident, taken by the caller. */
export function canTakeIncident(user: CurrentUser | null, incident: IncidentRef): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  if (incident.assigned_to !== null) return deny(DENY_REASONS.assign);
  return canAssign(user, incident, user.username);
}

/** Choosing any assignee from the dropdown (reassign / unassign). */
export function canReassign(user: CurrentUser | null): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  return isLead(user) ? ALLOW : deny(DENY_REASONS.assign);
}

/**
 * A PATCH /api/incidents/{id} body, checked like the server does: every
 * field against the incident's CURRENT state; any denial denies the request.
 */
export function canPatchIncident(
  user: CurrentUser | null,
  incident: IncidentRef,
  patch: { status?: unknown; assigned_to?: string | null },
): Decision {
  if ('status' in patch) {
    const d = canWorkOnIncident(user, incident);
    if (!d.allowed) return d;
  }
  if ('assigned_to' in patch) {
    const d = canAssign(user, incident, patch.assigned_to ?? null);
    if (!d.allowed) return d;
  }
  return user ? ALLOW : deny(DENY_REASONS.notAuthenticated);
}

/** Creating users, changing roles, deleting users: admin only. */
export function canManageUsers(user: CurrentUser | null): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  return user.role === 'admin' ? ALLOW : deny(DENY_REASONS.admin);
}

/** POST /api/users: admin only, and never as an admin (single admin). */
export function canCreateUser(user: CurrentUser | null, body: { role?: unknown }): Decision {
  const d = canManageUsers(user);
  if (!d.allowed) return d;
  return body.role === 'admin' ? deny(DENY_REASONS.adminRoleFixed) : ALLOW;
}

/** DELETE /api/users/{username}: admin only, and never the admin account. */
export function canDeleteUser(user: CurrentUser | null, target: Pick<UserSummary, 'role'> | undefined): Decision {
  const d = canManageUsers(user);
  if (!d.allowed) return d;
  return target?.role === 'admin' ? deny(DENY_REASONS.adminUndeletable) : ALLOW;
}

/** The Users screen: admins manage everyone; managers reset analysts' passwords. */
export function canOpenUserAdmin(user: CurrentUser | null): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  return isLead(user) ? ALLOW : deny(DENY_REASONS.admin);
}

/**
 * PATCH /api/users/{username} (backend: check_user_update). Admins change
 * role/password of anyone; a manager may only reset an analyst's password,
 * with nothing else in the request. An unknown target is refused to managers.
 * Single admin: the admin role is never granted or removed, by anyone.
 * Nobody resets their OWN password here (no current password is asked).
 */
export function canUpdateUser(
  user: CurrentUser | null,
  target: Pick<UserSummary, 'role' | 'username'> | undefined,
  body: object,
): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  if (!isLead(user)) return deny(DENY_REASONS.admin);
  // Your own password: only in Settings, which asks for the current one.
  if (target?.username === user.username && 'password' in body) return deny(DENY_REASONS.ownPasswordInSettings);
  if (user.role === 'admin') {
    const newRole = (body as { role?: unknown }).role;
    const changesRole = newRole !== undefined && target !== undefined && newRole !== target.role;
    if (changesRole && (newRole === 'admin' || target.role === 'admin')) return deny(DENY_REASONS.adminRoleFixed);
    return ALLOW;
  }
  const keys = Object.keys(body);
  const passwordOnly = keys.length === 1 && keys[0] === 'password';
  return passwordOnly && target?.role === 'analyst' ? ALLOW : deny(DENY_REASONS.managerResetOnly);
}

/** Detection rules and behavioral settings. */
export function canManageConfiguration(user: CurrentUser | null): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  return user.role === 'admin' ? ALLOW : deny(DENY_REASONS.admin);
}
