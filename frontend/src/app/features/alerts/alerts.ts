import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  DestroyRef,
  OnInit,
} from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import {
  AlertStatus,
  AlertSummaryMetrics,
  DetectionSource,
  DETECTION_SOURCE_LABELS,
  SEVERITY_COLORS,
  ThreatAlert,
} from '../../shared/models/threat.models';
import { AlertDetailDrawerComponent } from './alert-detail-drawer/alert-detail-drawer.component';

type SevFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

const DETECTION_SOURCES: DetectionSource[] = [
  'sigma_rule', 'behavioral_detection', 'threat_intelligence',
  'correlation_engine', 'yara_detection',
];

const DRAWER_MIN = 320;
const DRAWER_MAX = 700;

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [TitleCasePipe, RouterLink, AlertDetailDrawerComponent],
  templateUrl: './alerts.html',
  styleUrl: './alerts.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:mousemove)': 'onMouseMove($event)',
    '(document:mouseup)': 'onMouseUp()',
  },
})
export class Alerts implements OnInit {
  private store      = inject(ThreatStoreService);
  private destroyRef = inject(DestroyRef);

  drawerWidth   = signal(420);
  private dragging      = false;
  private dragStartX    = 0;
  private dragStartWidth = 0;

  readonly statusFilter = signal<AlertStatus | 'all'>('all');
  readonly sevFilter    = signal<SevFilter>('all');
  readonly sourceFilter = signal<DetectionSource | 'all'>('all');
  readonly caseMap      = signal<Record<string, string>>({});
  readonly selectedAlert  = signal<ThreatAlert | null>(null);
  readonly summaryMetrics = signal<AlertSummaryMetrics | null>(null);
  readonly loading        = signal(true);

  readonly severities: SevFilter[] = ['all', 'critical', 'high', 'medium', 'low'];
  readonly detectionSources = DETECTION_SOURCES;
  readonly detectionSourceLabel = (s: string) => DETECTION_SOURCE_LABELS[s] ?? s;

  readonly filtered = computed(() => {
    const status = this.statusFilter();
    const sev    = this.sevFilter();
    const source = this.sourceFilter();
    return this.store.alerts().filter(a =>
      (status === 'all' || a.status === status) &&
      (sev    === 'all' || a.severity === sev)  &&
      (source === 'all' || a.detection_source === source)
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

  ngOnInit() {
    this.store.fetchAlerts()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(alerts => {
        this.store.alerts.set(alerts);
        this.loading.set(false);
      });

    this.store.fetchAlertSummary()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(m => this.summaryMetrics.set(m));
  }

  timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    return `${Math.floor(m / 60)}h ago`;
  }

  selectAlert(alert: ThreatAlert) {
    this.selectedAlert.set(alert);
  }

  closeDrawer() {
    this.selectedAlert.set(null);
  }

  onCaseCreated(alertId: string, incidentId: string) {
    this.caseMap.update(m => ({ ...m, [alertId]: incidentId }));
  }

  acknowledge(id: string, event: Event) {
    event.stopPropagation();
    this.store.acknowledgeAlert(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(updated => {
        this.store.alerts.update(list => list.map(a => a.id === id ? updated : a));
        if (this.selectedAlert()?.id === id) this.selectedAlert.set(updated);
      });
  }

  dismiss(id: string, event: Event) {
    event.stopPropagation();
    this.store.dismissAlert(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        this.store.alerts.update(list => list.filter(a => a.id !== id));
        if (this.selectedAlert()?.id === id) this.selectedAlert.set(null);
      });
  }

  createCase(id: string, event: Event) {
    event.stopPropagation();
    this.store.createCaseFromAlert(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(incident => {
        this.caseMap.update(m => ({ ...m, [id]: incident.id }));
      });
  }

  startResize(e: MouseEvent) {
    this.dragging      = true;
    this.dragStartX    = e.clientX;
    this.dragStartWidth = this.drawerWidth();
    e.preventDefault();
    e.stopPropagation();
  }

  onMouseMove(e: MouseEvent) {
    if (!this.dragging) return;
    const delta = this.dragStartX - e.clientX;
    this.drawerWidth.set(Math.min(DRAWER_MAX, Math.max(DRAWER_MIN, this.dragStartWidth + delta)));
  }

  onMouseUp() {
    this.dragging = false;
  }
}
