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

  paused = signal(false);
  filterLevel = signal<ThreatLevel | 'all'>('all');
  acknowledged = signal<Set<string>>(new Set());
  private snapshot = signal<ThreatEvent[]>([]);

  filtered = computed(() => {
    const level = this.filterLevel();
    const list = this.paused() ? this.snapshot() : this.store.events();
    return list.filter((e) => level === 'all' || e.threat_level === level);
  });

  setFilter(level: ThreatLevel | 'all') {
    this.filterLevel.set(level);
  }

  acknowledge(e: ThreatEvent) {
    this.acknowledged.update((s) => new Set([...s, e.ip + e.timestamp]));
  }

  isAcknowledged(e: ThreatEvent): boolean {
    return this.acknowledged().has(e.ip + e.timestamp);
  }

  togglePause() {
    if (!this.paused()) {
      this.snapshot.set([...this.store.events()]);
    }
    this.paused.update((v) => !v);
  }
}
