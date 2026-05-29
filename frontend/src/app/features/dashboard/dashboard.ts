import { Component, computed, inject, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { ChartsColumnComponent } from './charts-column/charts-column.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [ChartsColumnComponent, DatePipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Dashboard {
  protected readonly store = inject(ThreatStoreService);

  readonly criticalEvents = computed(() =>
    this.store
      .events()
      .filter((e) => e.threat_level === 'critical')
      .slice(0, 30),
  );

  getSeverityClass(level: string): string {
    return `sev-${level}`;
  }

  getEventLabel(attackType: string): string {
    const labels: Record<string, string> = {
      SQLi: 'SQL Injection attempt',
      DDoS: 'DDoS flood detected',
      BruteForce: 'Brute force login',
      PortScan: 'Port scan observed',
      Malware: 'Malware beacon',
    };
    return labels[attackType] ?? 'Unknown event';
  }
}
