import { Component, inject, signal, computed, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { ThreatEvent, ThreatLevel } from '../../shared/models/threat.models';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './alerts.html',
  styleUrl: './alerts.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Alerts {
  protected readonly store = inject(ThreatStoreService);

  filterLevel = signal<ThreatLevel | 'all'>('all');
  dismissed = signal<Set<string>>(new Set());

  filtered = computed(() => {
    const level = this.filterLevel();
    const dis = this.dismissed();
    return this.store
      .events()
      .filter((e) => !dis.has(e.ip + e.timestamp))
      .filter((e) => level === 'all' || e.threat_level === level);
  });

  setFilter(level: ThreatLevel | 'all') {
    this.filterLevel.set(level);
  }

  dismiss(e: ThreatEvent) {
    this.dismissed.update((s) => new Set([...s, e.ip + e.timestamp]));
  }
}
