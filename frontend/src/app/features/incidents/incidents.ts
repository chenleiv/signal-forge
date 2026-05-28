import { Component, OnInit, OnDestroy, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { Incident, IncidentStatus } from '../../shared/models/threat.models';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-incidents',
  standalone: true,
  imports: [DatePipe, RouterLink],
  templateUrl: './incidents.html',
  styleUrl: './incidents.scss',
})
export class Incidents implements OnInit, OnDestroy {
  private http = inject(HttpClient);

  incidents = signal<Incident[]>([]);
  selected = signal<Incident | null>(null);

  private interval: ReturnType<typeof setInterval> | null = null;

  ngOnInit() {
    this.load();
    this.interval = setInterval(() => this.load(), 10_000);
  }

  ngOnDestroy() {
    if (this.interval) clearInterval(this.interval);
  }

  private load() {
    this.http.get<Incident[]>('/api/incidents').subscribe((d) => this.incidents.set(d));
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
