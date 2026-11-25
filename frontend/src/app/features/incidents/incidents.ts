import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { ExportMenuComponent } from '../../shared/ui/export-menu.component';
import { FilterPillsComponent } from '../../shared/ui/filter-pills.component';
import { DrawerResize } from '../../shared/ui/drawer-resize';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { timer } from 'rxjs';
import { Incident, SEVERITY_COLORS } from '../../shared/models/threat.models';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { IncidentDetailComponent } from './incident-detail/incident-detail.component';
import { downloadCsv, downloadJson, downloadMarkdown, downloadPdf } from '../../core/utils/export.utils';

/** One row of the JSON export: typed values, ISO time, null when unassigned. */
export interface IncidentExportItem {
  id: string;
  title: string;
  severity: Incident['severity'];
  status: Incident['status'];
  attack_type: Incident['attack_type'];
  source_region: string;
  event_count: number;
  assigned_to: string | null;
  created_at: string;
}

@Component({
  selector: 'app-incidents',
  standalone: true,
  imports: [DatePipe, IncidentDetailComponent, FilterPillsComponent, ExportMenuComponent],
  templateUrl: './incidents.html',
  styleUrl: './incidents.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:mousemove)': 'drawer.move($event)',
    '(document:mouseup)': 'drawer.end()',
  },
})
export class Incidents {
  incidents = signal<Incident[]>([]);
  loading   = signal(true);
  selected = signal<Incident | null>(null);
  searchText = signal('');
  statusFilter = signal('all');
  severityFilter = signal('all');
  readonly statuses = ['open', 'investigating', 'contained', 'closed'] as const;
  readonly severities = ['critical', 'high', 'medium', 'low'] as const;
  readonly drawer = new DrawerResize(500, 500, 700);
  toast = signal<string | null>(null);

  readonly filtered = computed(() => {
    const search = this.searchText().toLowerCase();
    const status = this.statusFilter();
    const severity = this.severityFilter();
    return this.incidents().filter(
      (i) =>
        (!search ||
          i.title.toLowerCase().includes(search) ||
          i.id.toLowerCase().includes(search)) &&
        (status === 'all' || i.status === status) &&
        (severity === 'all' || i.severity === severity),
    );
  });

  private destroyRef = inject(DestroyRef);
  private store = inject(ThreatStoreService);
  private route = inject(ActivatedRoute);

  private readonly exportHeaders = [
    'ID',
    'Title',
    'Severity',
    'Status',
    'Type',
    'Region',
    'Events',
    'Assigned',
    'Created',
  ];
  private get exportRows(): string[][] {
    return this.filtered().map((i) => [
      i.id,
      i.title,
      i.severity,
      i.status,
      i.attack_type,
      i.source_region,
      String(i.event_count),
      i.assigned_to ?? '—',
      new Date(i.created_at).toLocaleString(),
    ]);
  }

  constructor() {
    const targetId = this.route.snapshot.queryParamMap.get('id');
    const isExisting = this.route.snapshot.queryParamMap.get('existing') === '1';

    this.store
      .fetchIncidents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((d) => {
        this.incidents.set(d);
        this.loading.set(false);
        if (targetId) {
          const match = d.find((i) => i.id === targetId);
          if (match) {
            this.selected.set(match);
            if (isExisting) this.showToast(`Case ${targetId} already exists — opened existing`);
          }
        }
      });

    timer(30_000, 30_000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.refreshList());
  }

  open(inc: Incident) {
    this.selected.set(inc);
  }
  close() {
    this.selected.set(null);
  }

  onIncidentChange(updated: Incident) {
    this.selected.set(updated);
    this.incidents.update((list) => list.map((i) => (i.id === updated.id ? updated : i)));
  }

  exportCsv() {
    downloadCsv(this.exportHeaders, this.exportRows, 'incidents.csv');
  }
  exportPdf() {
    downloadPdf(
      'SignalForge — Incident Report',
      this.exportHeaders,
      this.exportRows,
      'incidents.pdf',
    );
  }
  exportJson() {
    downloadJson('incidents', this.exportItems, 'incidents.json');
  }
  exportMarkdown() {
    downloadMarkdown(
      'SignalForge — Incident Report',
      this.exportHeaders,
      this.exportRows,
      'incidents.md',
    );
  }

  private get exportItems(): IncidentExportItem[] {
    return this.filtered().map((i) => ({
      id: i.id,
      title: i.title,
      severity: i.severity,
      status: i.status,
      attack_type: i.attack_type,
      source_region: i.source_region,
      event_count: i.event_count,
      assigned_to: i.assigned_to ?? null,
      created_at: new Date(i.created_at).toISOString(),
    }));
  }

  readonly severityColor = (sev: string) => SEVERITY_COLORS[sev] ?? 'var(--c-muted)';

  private refreshList() {
    this.store
      .fetchIncidents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((d) => {
        this.incidents.set(d);
        const sel = this.selected();
        if (sel) {
          const updated = d.find((i) => i.id === sel.id);
          if (updated) this.selected.set(updated);
        }
      });
  }

  showToast(msg: string) {
    this.toast.set(msg);
    setTimeout(() => this.toast.set(null), 3500);
  }
}
