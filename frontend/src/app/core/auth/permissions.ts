import { Incident, UserSummary } from '../../shared/models/threat.models';

/**
 * The RBAC permission matrix, client side. Mirrors backend/authz.py and is
 * used by BOTH the UI (to hide/disable actions) and DemoSimulatorService (so
 * the demo never "succeeds" at something the real server would deny).
 *
 * UX only: the server is the security boundary and re-checks everything.
 * Reasons are the server's exact `detail` strings, so users see the same
 * message in the demo and against the real API.
 */

export type CurrentUser = UserSummary;

export type Decision = { allowed: true } | { allowed: false; reason: string };

export const DENY_REASONS = {
  notAuthenticated: 'Not authenticated',
  work: 'Only the assignee or an admin can change this incident',
  assign: 'Analysts can only take unassigned incidents for themselves',
  admin: 'Admin role required',
} as const;

const ALLOW: Decision = { allowed: true };
const deny = (reason: string): Decision => ({ allowed: false, reason });

type IncidentRef = Pick<Incident, 'assigned_to'>;

/** Status, notes and tasks: only the assignee or an admin. */
export function canWorkOnIncident(user: CurrentUser | null, incident: IncidentRef): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  if (user.role === 'admin' || incident.assigned_to === user.username) return ALLOW;
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
  if (user.role === 'admin') return ALLOW;
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
  return user.role === 'admin' ? ALLOW : deny(DENY_REASONS.assign);
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

/** Detection rules and behavioral settings. */
export function canManageConfiguration(user: CurrentUser | null): Decision {
  if (!user) return deny(DENY_REASONS.notAuthenticated);
  return user.role === 'admin' ? ALLOW : deny(DENY_REASONS.admin);
}
