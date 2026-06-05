import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  DestroyRef,
  OnInit,
  NgZone,
} from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import {
  AlertStatus,
  AlertSummaryMetrics,
  DetectionSource,
  SEVERITY_COLORS,
  ThreatAlert,
} from '../../shared/models/threat.models';
import { AlertDetailDrawerComponent } from './alert-detail-drawer/alert-detail-drawer.component';

type SevFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

const DETECTION_SOURCE_LABELS: Record<string, string> = {
  sigma_rule:           'Sigma Rule',
  behavioral_detection: 'Behavioral',
  threat_intelligence:  'Threat Intel',
  correlation_engine:   'Correlation',
  yara_detection:       'YARA',
};

const DETECTION_SOURCES: DetectionSource[] = [
  'sigma_rule', 'behavioral_detection', 'threat_intelligence',
  'correlation_engine', 'yara_detection',
];

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [TitleCasePipe, RouterLink, AlertDetailDrawerComponent],
  templateUrl: './alerts.html',
  styleUrl: './alerts.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
const DRAWER_MIN = 280;
const DRAWER_MAX = 700;

export class Alerts implements OnInit {
  private store      = inject(ThreatStoreService);
  private destroyRef = inject(DestroyRef);
  private zone       = inject(NgZone);

  readonly drawerWidth  = signal(420);
  readonly statusFilter = signal<AlertStatus | 'all'>('all');
  readonly sevFilter    = signal<SevFilter>('all');
  readonly sourceFilter = signal<DetectionSource | 'all'>('all');
  readonly caseMap      = signal<Record<string, string>>({});
  readonly selectedAlert = signal<ThreatAlert | null>(null);
  readonly summaryMetrics = signal<AlertSummaryMetrics | null>(null);

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

  startResize(event: MouseEvent) {
    event.preventDefault();
    const startX     = event.clientX;
    const startWidth = this.drawerWidth();

    const onMove = (e: MouseEvent) => {
      const delta = startX - e.clientX;
      const next  = Math.min(DRAWER_MAX, Math.max(DRAWER_MIN, startWidth + delta));
      this.drawerWidth.set(next);
    };

    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };

    this.zone.runOutsideAngular(() => {
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });

    this.destroyRef.onDestroy(onUp);
  }
}
