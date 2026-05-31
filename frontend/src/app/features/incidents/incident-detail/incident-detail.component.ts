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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { Incident, IncidentNote, IncidentStatus } from '../../../shared/models/threat.models';
import { ThreatStoreService } from '../../../core/services/threat-store.service';

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
  incident = input<Incident | null>(null);
  closed         = output<void>();
  incidentChange = output<Incident>();

  private store      = inject(ThreatStoreService);
  private router     = inject(Router);
  private destroyRef = inject(DestroyRef);

  notes        = signal<IncidentNote[]>([]);
  newNote      = signal('');
  completedTasks = signal<Set<number>>(new Set());
  timeline     = signal<TimelineEntry[]>([]);

  readonly tasks = computed(() =>
    RESPONSE_TASKS[this.incident()?.attack_type ?? 'SQLi'] ?? []
  );

  readonly statusFlow = STATUS_FLOW;

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

  close() { this.closed.emit(); }

  private patchAndEmit(patch: Parameters<ThreatStoreService['patchIncident']>[1], timelineLabel: string, timelineType: TimelineEntry['type']) {
    const inc = this.incident();
    if (!inc) return;
    this.store.patchIncident(inc.id, patch)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(updated => {
        this.incidentChange.emit(updated);
        this.timeline.update(tl => [{ label: timelineLabel, at: updated.updated_at, type: timelineType }, ...tl]);
      });
  }

  updateStatus(status: IncidentStatus) {
    if (this.incident()?.status === status) return;
    this.patchAndEmit({ status }, `Status → ${status}`, 'status');
  }

  readonly analysts = ['analyst1', 'analyst2', 'analyst3', 'analyst4', 'analyst5'];

  updateAssignee(value: string) {
    const assigned_to = value || null;
    this.patchAndEmit({ assigned_to }, `Assigned → ${assigned_to ?? 'Unassigned'}`, 'assign');
  }

  toggleTask(index: number) {
    const inc = this.incident();
    if (!inc) return;
    this.completedTasks.update(s => {
      const next = new Set(s);
      next.has(index) ? next.delete(index) : next.add(index);
      this.store.updateIncidentTasks(inc.id, [...next])
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe();
      return next;
    });
  }

  addNote() {
    const text = this.newNote().trim();
    const inc  = this.incident();
    if (!text || !inc) return;
    this.store.addIncidentNote(inc.id, text)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(note => {
        this.notes.update(n => [...n, note]);
        this.newNote.set('');
        this.timeline.update(tl => [
          { label: `Note added by ${note.author}`, at: note.at, type: 'note' },
          ...tl,
        ]);
      });
  }

  investigateIp(ip: string) {
    this.router.navigate(['/threats'], { queryParams: { ip } });
  }

  severityColor(sev: string): string {
    const map: Record<string, string> = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#60a5fa' };
    return map[sev] ?? '#9ca3af';
  }
}
