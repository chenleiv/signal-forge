import { Component, inject, signal, ChangeDetectionStrategy, DestroyRef, HostListener } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe, TitleCasePipe } from '@angular/common';
import { Incident } from '../../shared/models/threat.models';
import { timer } from 'rxjs';
import { ThreatStoreService } from '../../core/services/threat-store.service';

@Component({
  selector: 'app-incidents',
  standalone: true,
  imports: [DatePipe, TitleCasePipe],
  templateUrl: './incidents.html',
  styleUrl: './incidents.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Incidents {
  private destroyRef = inject(DestroyRef);
  private store = inject(ThreatStoreService);
  incidents = signal<Incident[]>([]);
  selected = signal<Incident | null>(null);
  detailWidth = signal(360);

  private dragging = false;
  private dragStartX = 0;
  private dragStartWidth = 0;

  ngOnInit() {
    timer(0, 30_000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.load());
  }

  private load() {
    this.store
      .fetchIncidents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((d) => {
        this.incidents.set(d);
        if (!this.selected() && d.length > 0) {
          this.selected.set(d[0]);
        }
      });
  }

  open(inc: Incident) { this.selected.set(inc); }
  close()             { this.selected.set(null); }

  startResize(e: MouseEvent) {
    this.dragging = true;
    this.dragStartX = e.clientX;
    this.dragStartWidth = this.detailWidth();
    e.preventDefault();
  }

  @HostListener('document:mousemove', ['$event'])
  onMouseMove(e: MouseEvent) {
    if (!this.dragging) return;
    const delta = this.dragStartX - e.clientX;
    this.detailWidth.set(Math.min(700, Math.max(240, this.dragStartWidth + delta)));
  }

  @HostListener('document:mouseup')
  onMouseUp() { this.dragging = false; }
}
