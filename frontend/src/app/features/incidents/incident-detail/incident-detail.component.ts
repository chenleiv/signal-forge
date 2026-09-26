import {
  Component,
  input,
  output,
  inject,
  signal,
  computed,
  effect,
  DestroyRef,
  ChangeDetectionStrategy,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { Incident, IncidentNote, IncidentStatus, SEVERITY_COLORS } from '../../../shared/models/threat.models';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { AuthService } from '../../../core/services/auth';
import {
  Decision,
  canAssign,
  canReassign,
  canTakeIncident,
  canWorkOnIncident,
} from '../../../core/auth/permissions';

const RESPONSE_TASKS: Record<string, string[]> = {
  SQLi:       ['Isolate source IP', 'Review DB query logs', 'Check WAF rules', 'Patch vulnerable endpoints', 'Notify DBA team'],
  DDoS:       ['Enable rate limiting', 'Block source CIDR', 'Alert upstream provider', 'Scale load balancers', 'Monitor bandwidth'],
  BruteForce: ['Block source IP', 'Reset targeted accounts', 'Enforce MFA', 'Review auth logs', 'Notify account owners'],
  PortScan:   ['Block source IP', 'Audit exposed ports', 'Update firewall rules', 'Check IDS alerts'],
  Malware:    ['Isolate affected host', 'Run AV/EDR scan', 'Collect forensic artifacts', 'Revoke compromised creds', 'Notify IR team'],
};

const STATUS_FLOW: IncidentStatus[] = ['open', 'investigating', 'contained', 'closed'];

export interface TimelineEntry {
  label: string;
  at: string;
  type: 'create' | 'status' | 'note' | 'assign';
}

@Component({
  selector: 'app-incident-detail',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './incident-detail.component.html',
  styleUrl: './incident-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IncidentDetailComponent {
  // ── inputs / outputs ──────────────────────────────────────────
  incident       = input<Incident | null>(null);
  closed         = output<void>();
  incidentChange = output<Incident>();

  // ── public signals ────────────────────────────────────────────
  notes          = signal<IncidentNote[]>([]);
  newNote        = signal('');
  completedTasks = signal<Set<number>>(new Set());
  timeline       = signal<TimelineEntry[]>([]);

  readonly tasks      = computed(() => RESPONSE_TASKS[this.incident()?.attack_type ?? 'SQLi'] ?? []);
  readonly statusFlow = STATUS_FLOW;

  // ── private injections ────────────────────────────────────────
  private readonly store      = inject(ThreatStoreService);
  private readonly router     = inject(Router);
  private readonly auth       = inject(AuthService);

  /** Assignable users; the server validates assigned_to against the same list. */
  readonly users = toSignal(this.store.getUsers(), { initialValue: [] });
  private readonly destroyRef = inject(DestroyRef);

  // ── permissions (UX only; the server re-checks every write) ──
  private readonly user = this.auth.currentUser;
  readonly work     = computed(() => this.decide(inc => canWorkOnIncident(this.user(), inc)));
  readonly take     = computed(() => this.decide(inc => canTakeIncident(this.user(), inc)));
  readonly reassign = computed(() => canReassign(this.user()));
  /** Tooltip text for a disabled control, or null when allowed. */
  readonly reason   = (d: Decision): string | null => (d.allowed ? null : d.reason);

  // ── constructor ───────────────────────────────────────────────
  constructor() {
    effect(() => {
      const inc = this.incident();
      if (!inc) return;
      this.notes.set(inc.notes ?? []);
      this.completedTasks.set(new Set<number>(inc.completed_tasks ?? []));
      this.timeline.set([
        { label: 'Incident created', at: inc.created_at, type: 'create' },
        ...(inc.updated_at !== inc.created_at
          ? [{ label: `Status: ${inc.status}`, at: inc.updated_at, type: 'status' as const }]
          : []),
      ]);
    });
  }

  // ── public methods ────────────────────────────────────────────
  close() { this.closed.emit(); }

  // Every handler re-checks its permission: aria-disabled controls stay clickable.
  updateStatus(status: IncidentStatus) {
    if (!this.work().allowed || this.incident()?.status === status) return;
    this.patchAndEmit({ status }, `Status → ${status}`, 'status');
  }

  updateAssignee(value: string) {
    const inc = this.incident();
    const assigned_to = value || null;
    if (!inc || !canAssign(this.user(), inc, assigned_to).allowed) return;
    this.patchAndEmit({ assigned_to }, `Assigned → ${assigned_to ?? 'Unassigned'}`, 'assign');
  }

  takeCase() {
    const me = this.user();
    if (!me || !this.take().allowed) return;
    this.patchAndEmit({ assigned_to: me.username }, `Taken by ${me.display_name}`, 'assign');
  }

  toggleTask(index: number) {
    const inc = this.incident();
    if (!inc || !this.work().allowed) return;
    const next = new Set(this.completedTasks());
    next.has(index) ? next.delete(index) : next.add(index);
    this.completedTasks.set(next);
    this.store.updateIncidentTasks(inc.id, [...next])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe();
  }

  addNote() {
    const text = this.newNote().trim();
    const inc  = this.incident();
    if (!text || !inc || !this.work().allowed) return;
    this.store.addIncidentNote(inc.id, text)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(note => {
        this.notes.update(n => [...n, note]);
        this.newNote.set('');
        this.timeline.update(tl => [{ label: `Note added by ${note.author}`, at: note.at, type: 'note' }, ...tl]);
      });
  }

  investigateIp(ip: string) { this.router.navigate(['/threats'], { queryParams: { ip } }); }

  readonly severityColor = (sev: string) => SEVERITY_COLORS[sev] ?? '#9ca3af';

  displayName(username: string | null): string {
    if (!username) return 'Unassigned';
    return this.users().find(u => u.username === username)?.display_name ?? username;
  }

  // ── private methods ───────────────────────────────────────────
  private decide(check: (inc: Incident) => Decision): Decision {
    const inc = this.incident();
    return inc ? check(inc) : { allowed: false, reason: 'No incident selected' };
  }

  private patchAndEmit(patch: Parameters<ThreatStoreService['patchIncident']>[1], timelineLabel: string, timelineType: TimelineEntry['type']) {
    const inc = this.incident();
    if (!inc) return;
    this.store.patchIncident(inc.id, patch)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next:  updated => { this.incidentChange.emit(updated); this.timeline.update(tl => [{ label: timelineLabel, at: updated.updated_at, type: timelineType }, ...tl]); },
        error: () => console.error('[IncidentDetail] patch failed'),
      });
  }
}
