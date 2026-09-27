import { Injectable, inject } from '@angular/core';
import { HttpRequest } from '@angular/common/http';
import { ThreatStoreService } from './threat-store.service';
import { AuthService } from './auth';
import {
  Decision,
  canManageConfiguration,
  canCreateUser,
  canDeleteUser,
  canUpdateUser,
  canPatchIncident,
  canWorkOnIncident,
} from '../auth/permissions';
import {
  AttackType,
  Incident,
  IncidentNote,
  ThreatAlert,
  ThreatLevel,
  UserSummary,
} from '../../shared/models/threat.models';

/** Result of simulating a write: the fake response body, or null if not handled. */
export type SimResult = { body: unknown } | null;

type Json = Record<string, unknown>;

const ATTACK_TYPES: readonly AttackType[] = [
  'SQLi', 'DDoS', 'BruteForce', 'PortScan', 'Malware', 'RepeatedIP', 'Escalation',
];

/**
 * In-browser simulation of the core analyst actions for the public demo:
 * alert triage, incident handling and IP blocking. Other writes are not
 * simulated; the server rejects them and the UI shows a notice instead.
 *
 * Writes never reach the server. Instead this service keeps a local
 * "overlay" (created / updated / deleted items) and applies it to the
 * matching GET responses, so the UI stays consistent across polling and
 * navigation. Everything resets on page reload.
 *
 * Permissions: `authorize` applies the same matrix as the server (shared
 * helper in core/auth/permissions.ts), so the demo never "succeeds" at an
 * action the real system would deny.
 *
 * Security note: this is UX only. The server independently rejects writes
 * in demo mode, so bypassing this code gains an attacker nothing.
 */
@Injectable({ providedIn: 'root' })
export class DemoSimulatorService {
  private store = inject(ThreatStoreService);
  private auth  = inject(AuthService);
  private seq = 0;

  // Last server copy of each item, so PATCH can return a full object.
  private seenAlerts    = new Map<string, ThreatAlert>();
  private seenIncidents = new Map<string, Incident>();
  private seenUsers     = new Map<string, UserSummary>();

  // Local overlay.
  private blocked        = new Map<string, boolean>();
  private alertPatches   = new Map<string, Partial<ThreatAlert>>();
  private incCreated: Incident[] = [];
  private incPatches     = new Map<string, Partial<Incident>>();
  private incNotes       = new Map<string, IncidentNote[]>();
  private ipCases        = new Map<string, string>();

  // ── Permissions ───────────────────────────────────────────

  /** Would the real server allow this write for the current user? */
  authorize(req: HttpRequest<unknown>, path: string): Decision {
    const user = this.auth.currentUser();
    const m = req.method;
    const body = (req.body ?? {}) as Json;
    let p: RegExpMatchArray | null;

    if (/^\/api\/(rules(\/[^/]+)?|behavioral\/settings)$/.test(path) && m !== 'GET') {
      return canManageConfiguration(user);
    }
    if (path === '/api/users' && m === 'POST') return canCreateUser(user, body);
    if ((p = path.match(/^\/api\/users\/([^/]+)$/))) {
      const target = this.seenUsers.get(decodeURIComponent(p[1]));
      if (m === 'DELETE') return canDeleteUser(user, target);
      if (m === 'PATCH') return canUpdateUser(user, target, body);
    }
    if ((p = path.match(/^\/api\/incidents\/([^/]+)\/(notes|tasks)$/))) {
      const inc = this.currentIncident(p[1]);
      if (inc) return canWorkOnIncident(user, inc);
    } else if ((p = path.match(/^\/api\/incidents\/([^/]+)$/)) && m === 'PATCH') {
      const inc = this.currentIncident(p[1]);
      if (inc) return canPatchIncident(user, inc, body as { status?: unknown; assigned_to?: string | null });
    }
    return { allowed: true };
  }

  // ── Writes ────────────────────────────────────────────────

  simulate(req: HttpRequest<unknown>, path: string): SimResult {
    const m = req.method;
    const body = (req.body ?? {}) as Json;
    let p: RegExpMatchArray | null;

    if ((p = path.match(/^\/api\/ip\/([^/]+)\/block$/)) && (m === 'POST' || m === 'DELETE')) {
      const ip = decodeURIComponent(p[1]);
      this.blocked.set(ip, m === 'POST');
      return { body: { blocked: m === 'POST', ip } };
    }

    if ((p = path.match(/^\/api\/alerts\/([^/]+)$/)) && m === 'PATCH') {
      const id = p[1];
      const status = body['status'] === 'dismissed' ? 'dismissed' : 'acknowledged';
      const patch: Partial<ThreatAlert> = { status };
      if (status === 'acknowledged') patch.acknowledged_at = this.now();
      this.alertPatches.set(id, { ...this.alertPatches.get(id), ...patch });
      const base = this.seenAlerts.get(id) ?? this.store.alerts().find(a => a.id === id);
      return { body: { ...base, ...this.alertPatches.get(id) } };
    }

    if ((p = path.match(/^\/api\/alerts\/([^/]+)\/case$/)) && m === 'POST') {
      const alert = this.seenAlerts.get(p[1]) ?? this.store.alerts().find(a => a.id === p![1]);
      const ip = alert?.ip ?? null;
      return { body: this.openCase(ip, alert?.severity, alert?.type, `Alert: ${alert?.message ?? p[1]}`) };
    }

    if (path === '/api/incidents/from-ip' && m === 'POST') {
      const ip = String(body['ip'] ?? 'unknown');
      return { body: this.openCase(ip) };
    }

    if ((p = path.match(/^\/api\/incidents\/([^/]+)\/notes$/)) && m === 'POST') {
      const note: IncidentNote = {
        author: this.auth.currentUser()?.username ?? 'unknown',
        text: String(body['text'] ?? ''),
        at: this.now(),
      };
      this.incNotes.set(p[1], [...(this.incNotes.get(p[1]) ?? []), note]);
      return { body: note };
    }

    if ((p = path.match(/^\/api\/incidents\/([^/]+)\/tasks$/)) && m === 'PATCH') {
      const completed = Array.isArray(body['completed_tasks'])
        ? (body['completed_tasks'] as unknown[]).filter((n): n is number => typeof n === 'number')
        : [];
      this.patchIncident(p[1], { completed_tasks: completed });
      return { body: { completed_tasks: completed } };
    }

    if ((p = path.match(/^\/api\/incidents\/([^/]+)$/)) && m === 'PATCH') {
      const patch: Partial<Incident> = {};
      if (typeof body['status'] === 'string') patch.status = body['status'] as Incident['status'];
      if ('assigned_to' in body) patch.assigned_to = (body['assigned_to'] as string | null) ?? null;
      return { body: this.patchIncident(p[1], patch) };
    }

    return null;
  }

  // ── Reads: apply the local overlay to server data ─────────

  overlay(path: string, body: unknown): unknown {
    let p: RegExpMatchArray | null;

    if (path === '/api/alerts' && Array.isArray(body)) {
      (body as ThreatAlert[]).forEach(a => this.seenAlerts.set(a.id, a));
      return (body as ThreatAlert[])
        .map(a => ({ ...a, ...this.alertPatches.get(a.id) }))
        .filter(a => a.status !== 'dismissed');
    }

    if (path === '/api/users' && Array.isArray(body)) {
      (body as UserSummary[]).forEach(u => this.seenUsers.set(u.username, u));
      return body;
    }

    if (path === '/api/incidents' && Array.isArray(body)) {
      (body as Incident[]).forEach(i => this.seenIncidents.set(i.id, i));
      return [...this.incCreated, ...(body as Incident[])].map(i => this.withIncidentOverlay(i));
    }

    if ((p = path.match(/^\/api\/ip\/([^/]+)\/block$/)) && body && typeof body === 'object') {
      const ip = decodeURIComponent(p[1]);
      return this.blocked.has(ip) ? { ...(body as Json), blocked: this.blocked.get(ip) } : body;
    }

    if ((p = path.match(/^\/api\/ip\/([^/]+)\/case$/)) && body && typeof body === 'object') {
      const caseId = this.ipCases.get(decodeURIComponent(p[1]));
      return caseId ? { case_id: caseId } : body;
    }

    return body;
  }

  // ── Helpers ───────────────────────────────────────────────

  private openCase(
    ip: string | null,
    severity?: ThreatLevel,
    type?: string,
    title?: string,
  ): Incident & { existing: boolean } {
    const existingId = ip ? this.ipCases.get(ip) : undefined;
    const existing = existingId ? this.incCreated.find(i => i.id === existingId) : undefined;
    if (existing) return { ...this.withIncidentOverlay(existing), existing: true };

    const events = ip ? this.store.events().filter(e => e.ip === ip) : [];
    const latest = events[0];
    const attack: AttackType =
      (ATTACK_TYPES as readonly string[]).includes(type ?? '') ? (type as AttackType)
      : latest?.attack_type ?? 'PortScan';
    const now = this.now();

    const incident: Incident = {
      id: `INC-DEMO-${++this.seq}`,
      title: title ?? `Suspicious activity from ${ip}`,
      severity: severity ?? latest?.threat_level ?? 'medium',
      status: 'open',
      attack_type: attack,
      source_ip: ip ?? undefined,
      source_region: latest?.region ?? 'US',
      event_count: events.length,
      assigned_to: this.auth.currentUser()?.username ?? null,  // creator, like the server
      created_at: now,
      updated_at: now,
      mitre_tags: [],
      notes: [],
      completed_tasks: [],
    };
    this.incCreated.unshift(incident);
    if (ip) this.ipCases.set(ip, incident.id);
    return { ...incident, existing: false };
  }

  /** The incident as the UI currently sees it (server copy + local overlay). */
  private currentIncident(id: string): Incident | undefined {
    const base = this.incCreated.find(i => i.id === id) ?? this.seenIncidents.get(id);
    return base ? this.withIncidentOverlay(base) : undefined;
  }

  private patchIncident(id: string, patch: Partial<Incident>): Incident {
    const merged = { ...this.incPatches.get(id), ...patch, updated_at: this.now() };
    this.incPatches.set(id, merged);
    const base = this.incCreated.find(i => i.id === id) ?? this.seenIncidents.get(id);
    return this.withIncidentOverlay({ ...(base as Incident), id });
  }

  private withIncidentOverlay(i: Incident): Incident {
    const notes = this.incNotes.get(i.id);
    return {
      ...i,
      ...this.incPatches.get(i.id),
      notes: notes ? [...(i.notes ?? []), ...notes] : i.notes,
    };
  }

  private now(): string {
    return new Date().toISOString();
  }
}
