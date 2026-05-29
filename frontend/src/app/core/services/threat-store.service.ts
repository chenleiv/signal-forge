import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import {
  IpHistory,
  ThreatEvent,
  ThreatLevel,
  ThreatStats,
  Incident,
} from '../../shared/models/threat.models';
import { SettingsService } from './settings.service';

@Injectable({ providedIn: 'root' })
export class ThreatStoreService {
  private http = inject(HttpClient);
  private settingsSvc = inject(SettingsService);

  readonly events = signal<ThreatEvent[]>([]);
  readonly stats = signal<ThreatStats | null>(null);

  readonly criticalCount = computed(
    () => this.events().filter((e) => e.threat_level === 'critical').length,
  );
  readonly highCount = computed(
    () => this.events().filter((e) => e.threat_level === 'high').length,
  );
  readonly trackedIPs = computed(() => new Set(this.events().map((e) => e.ip)).size);

  readonly eventsPerMinute = computed(() => {
    const buckets = this.stats()?.events_per_min;
    if (!buckets?.length) return 0;
    return buckets[buckets.length - 1].count;
  });

  readonly severityColor: Record<ThreatLevel, string> = {
    critical: '#ff2d55',
    high: '#ff6b00',
    medium: '#ffcc00',
    low: '#00d4ff',
  };

  addEvent(event: ThreatEvent) {
    const size = this.settingsSvc.settings().bufferSize;
    this.events.update((list) => [event, ...list].slice(0, size));
  }

  refreshStats() {
    this.http.get<ThreatStats>('/api/stats').subscribe((s) => this.stats.set(s));
  }

  fetchIpHistory(ip: string) {
    return this.http.get<IpHistory>(`/api/ip/${ip}/history`);
  }

  fetchAiSummary(ip: string) {
    return this.http.get<{ summary: string | null }>(`/api/ip/${ip}/ai-summary`);
  }

  executeCommand(command: string) {
    return this.http.post<{ output: string }>('/api/command', { command });
  }

  fetchIncidents() {
    return this.http.get<Incident[]>('/api/incidents');
  }
}
