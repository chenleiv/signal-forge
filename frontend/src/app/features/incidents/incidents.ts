import { Component, inject, signal, ChangeDetectionStrategy, DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpClient } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { Incident, IncidentStatus } from '../../shared/models/threat.models';
import { RouterLink } from '@angular/router';
import { timer } from 'rxjs';

@Component({
  selector: 'app-incidents',
  standalone: true,
  imports: [DatePipe, RouterLink],
  templateUrl: './incidents.html',
  styleUrl: './incidents.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Incidents {
  private destroyRef = inject(DestroyRef);
  protected readonly http = inject(HttpClient);
  incidents = signal<Incident[]>([]);
  selected = signal<Incident | null>(null);

  ngOnInit() {
    timer(0, 30_000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.load());
  }

  private load() {
    this.http
      .get<Incident[]>('/api/incidents')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((d) => this.incidents.set(d));
  }

  open(inc: Incident) {
    this.selected.set(inc);
  }
  close() {
    this.selected.set(null);
  }

  statusColor(s: IncidentStatus): string {
    const map: Record<IncidentStatus, string> = {
      open: '#ff2d55',
      investigating: '#ff6b00',
      contained: '#ffcc00',
      closed: '#16a34a',
    };
    return map[s] ?? '#9ca3af';
  }
}
