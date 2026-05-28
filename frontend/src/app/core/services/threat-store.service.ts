import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { IpHistory, ThreatEvent, ThreatLevel, ThreatStats } from '../../shared/models/threat.models';

@Injectable({ providedIn: 'root' })
export class ThreatStoreService {
  private http = inject(HttpClient);

  readonly events = signal<ThreatEvent[]>([]);
  readonly stats = signal<ThreatStats | null>(null);

  readonly criticalCount = computed(
    () => this.events().filter(e => e.threat_level === 'critical').length
  );
  readonly highCount = computed(
    () => this.events().filter(e => e.threat_level === 'high').length
  );
  readonly trackedIPs = computed(
    () => new Set(this.events().map(e => e.ip)).size
  );
  readonly eventsPerMinute = computed(() => this.events().length);

  readonly severityColor: Record<ThreatLevel, string> = {
    critical: '#ff2d55',
    high:     '#ff6b00',
    medium:   '#ffcc00',
    low:      '#00d4ff',
  };

  addEvent(event: ThreatEvent) {
    this.events.update(list => [event, ...list].slice(0, 100));
  }

  refreshStats() {
    this.http.get<ThreatStats>('/api/stats').subscribe(s => this.stats.set(s));
  }

  fetchIpHistory(ip: string) {
    return this.http.get<IpHistory>(`/api/ip/${ip}/history`);
  }
}
