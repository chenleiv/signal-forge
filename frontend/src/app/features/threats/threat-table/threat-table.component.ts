import { Component, OnInit, output, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ThreatStats } from '../../../shared/models/threat.models';

interface IpRow {
  ip: string;
  count: number;
  score: number;
}

@Component({
  selector: 'app-threat-table',
  standalone: true,
  imports: [],
  templateUrl: './threat-table.component.html',
  styleUrl: './threat-table.component.scss',
})
export class ThreatTableComponent implements OnInit {
  private http = inject(HttpClient);

  rows: IpRow[] = [];
  loading = true;

  ipSelected = output<string>();

  ngOnInit() {
    this.http.get<ThreatStats>('/api/stats').subscribe({
      next: (stats) => {
        this.rows = stats.top_ips;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  selectIp(ip: string) {
    this.ipSelected.emit(ip);
  }

  scoreClass(score: number): string {
    if (score >= 80) return 'score-critical';
    if (score >= 60) return 'score-high';
    if (score >= 40) return 'score-medium';
    return 'score-low';
  }
}
