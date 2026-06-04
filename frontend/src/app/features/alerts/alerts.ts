import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AlertSource, AlertStatus, SEVERITY_COLORS } from '../../shared/models/threat.models';

type SevFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [TitleCasePipe],
  templateUrl: './alerts.html',
  styleUrl: './alerts.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Alerts {
  private store      = inject(ThreatStoreService);
  private destroyRef = inject(DestroyRef);

  readonly statusFilter = signal<AlertStatus | 'all'>('all');
  readonly sevFilter    = signal<SevFilter>('all');
  readonly sourceFilter = signal<AlertSource | 'all'>('all');
  readonly caseMap      = signal<Record<string, string>>({});

  readonly severities: SevFilter[] = ['all', 'critical', 'high', 'medium', 'low'];

  readonly filtered = computed(() => {
    const status = this.statusFilter();
    const sev    = this.sevFilter();
    const source = this.sourceFilter();
    return this.store.alerts().filter(a =>
      (status === 'all' || a.status === status) &&
      (sev    === 'all' || a.severity === sev)  &&
      (source === 'all' || a.source === source)
    );
  });

  readonly newCount = computed(() => this.store.newAlertCount());

  readonly emptyMessage = computed(() => {
    const hasFilters =
      this.statusFilter() !== 'all' ||
      this.sevFilter()    !== 'all' ||
      this.sourceFilter() !== 'all';
    return hasFilters
      ? 'no alerts match the current filters'
      : 'no alerts yet — behavioral detection is monitoring';
  });

  readonly severityColor = (sev: string) => SEVERITY_COLORS[sev] ?? SEVERITY_COLORS['low'];

  timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    return `${Math.floor(m / 60)}h ago`;
  }

  acknowledge(id: string) {
    this.store.acknowledgeAlert(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(updated => {
        this.store.alerts.update(list => list.map(a => a.id === id ? updated : a));
      });
  }

  dismiss(id: string) {
    this.store.dismissAlert(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        this.store.alerts.update(list => list.filter(a => a.id !== id));
      });
  }

  createCase(id: string) {
    this.store.createCaseFromAlert(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(incident => {
        this.caseMap.update(m => ({ ...m, [id]: incident.id }));
      });
  }
}
