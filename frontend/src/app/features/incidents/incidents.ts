import {
  Component,
  inject,
  signal,
  computed,
  OnInit,
  ChangeDetectionStrategy,
  DestroyRef,
  HostListener,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { timer } from 'rxjs';
import { Incident } from '../../shared/models/threat.models';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { IncidentDetailComponent } from './incident-detail/incident-detail.component';

@Component({
  selector: 'app-incidents',
  standalone: true,
  imports: [DatePipe, IncidentDetailComponent],
  templateUrl: './incidents.html',
  styleUrl: './incidents.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Incidents implements OnInit {
  private destroyRef = inject(DestroyRef);
  private store = inject(ThreatStoreService);
  private route = inject(ActivatedRoute);

  incidents = signal<Incident[]>([]);
  selected  = signal<Incident | null>(null);

  searchText     = signal('');
  statusFilter   = signal('all');
  severityFilter = signal('all');

  readonly filtered = computed(() => {
    const search   = this.searchText().toLowerCase();
    const status   = this.statusFilter();
    const severity = this.severityFilter();
    return this.incidents().filter(i =>
      (!search   || i.title.toLowerCase().includes(search) || i.id.toLowerCase().includes(search)) &&
      (status   === 'all' || i.status   === status) &&
      (severity === 'all' || i.severity === severity)
    );
  });
  drawerWidth = signal(500);
  toast = signal<string | null>(null);

  private dragging = false;
  private dragStartX = 0;
  private dragStartWidth = 0;

  ngOnInit() {
    const targetId = this.route.snapshot.queryParamMap.get('id');
    const isExisting = this.route.snapshot.queryParamMap.get('existing') === '1';

    this.store.fetchIncidents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((d) => {
        this.incidents.set(d);
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

  private refreshList() {
    this.store.fetchIncidents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((d) => {
        this.incidents.set(d);
        const sel = this.selected();
        if (sel) {
          const updated = d.find(i => i.id === sel.id);
          if (updated) this.selected.set(updated);
        }
      });
  }

  private showToast(msg: string) {
    this.toast.set(msg);
    setTimeout(() => this.toast.set(null), 3500);
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

  startResize(e: MouseEvent) {
    this.dragging = true;
    this.dragStartX = e.clientX;
    this.dragStartWidth = this.drawerWidth();
    e.preventDefault();
    e.stopPropagation();
  }

  @HostListener('document:mousemove', ['$event'])
  onMouseMove(e: MouseEvent) {
    if (!this.dragging) return;
    const delta = this.dragStartX - e.clientX;
    this.drawerWidth.set(Math.min(700, Math.max(500, this.dragStartWidth + delta)));
  }

  @HostListener('document:mouseup')
  onMouseUp() {
    this.dragging = false;
  }

  severityColor(sev: string): string {
    const map: Record<string, string> = {
      critical: '#ef4444',
      high: '#f97316',
      medium: '#f59e0b',
      low: '#60a5fa',
    };
    return map[sev] ?? '#9ca3af';
  }
}
