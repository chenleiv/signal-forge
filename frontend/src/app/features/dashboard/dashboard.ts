import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ThreatsService } from '../../core/services/threats.service';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { ChartsColumnComponent } from './charts-column/charts-column.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [ChartsColumnComponent, DatePipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit, OnDestroy {
  private ws    = inject(ThreatsService);
  readonly store = inject(ThreatStoreService);

  ngOnInit() {
    this.ws.connect();
  }

  ngOnDestroy() {
    this.ws.disconnect();
  }

  // ── Template helpers ───────────────────────────────────────

  getTimestamp(): string {
    return new Date().toLocaleTimeString('he-IL', { hour12: false });
  }

  getSeverityClass(level: string): string {
    return `sev-${level}`;
  }

  getEventLabel(attackType: string): string {
    const labels: Record<string, string> = {
      SQLi:       'SQL Injection attempt',
      DDoS:       'DDoS flood detected',
      BruteForce: 'Brute force login',
      PortScan:   'Port scan observed',
      Malware:    'Malware beacon',
    };
    return labels[attackType] ?? 'Unknown event';
  }
}
