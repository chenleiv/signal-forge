import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import {
  IpHistory,
  IpGeo,
  RelatedIp,
  ThreatEvent,
  ThreatLevel,
  ThreatStats,
  Incident,
  IncidentNote,
  IncidentStatus,
  NetworkNode,
  NetworkLink,
  HuntQuery,
  SavedHunt,
  HuntResult,
  DetectionRule,
} from '../../shared/models/threat.models';
import { SettingsService } from './settings.service';

@Injectable({ providedIn: 'root' })
export class ThreatStoreService {
  private http = inject(HttpClient);
  private settingsSvc = inject(SettingsService);

  readonly events = signal<ThreatEvent[]>([]);
  readonly stats = signal<ThreatStats | null>(null);
  readonly frozen = signal(false);

  readonly criticalCount = computed(
    () => this.events().filter((e) => e.threat_level === 'critical').length,
  );
  readonly highCount = computed(
    () => this.events().filter((e) => e.threat_level === 'high').length,
  );
  readonly trackedIPs = computed(() => new Set(this.events().map((e) => e.ip)).size);

  readonly activeRegions = computed(() => new Set(this.events().map((e) => e.region)).size);

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
    if (this.frozen()) return;
    const size = this.settingsSvc.settings().bufferSize;
    this.events.update((list) => [event, ...list].slice(0, size));
  }

  toggleFreeze() {
    this.frozen.update((v) => !v);
  }

  refreshStats() {
    return this.http.get<ThreatStats>('/api/stats');
  }

  fetchIpHistory(ip: string) {
    return this.http.get<IpHistory>(`/api/ip/${ip}/history`);
  }

  fetchAiSummary(ip: string) {
    return this.http.get<{ summary: string | null }>(`/api/ip/${ip}/ai-summary`);
  }

  fetchIpGeo(ip: string) {
    return this.http.get<IpGeo>(`/api/ip/${ip}/geo`);
  }

  fetchRelatedIps(ip: string) {
    return this.http.get<{ related: RelatedIp[] }>(`/api/ip/${ip}/related`);
  }

  getBlockStatus(ip: string) {
    return this.http.get<{ blocked: boolean; ip: string }>(`/api/ip/${ip}/block`);
  }

  blockIp(ip: string) {
    return this.http.post<{ blocked: boolean; ip: string }>(`/api/ip/${ip}/block`, {});
  }

  unblockIp(ip: string) {
    return this.http.delete<{ blocked: boolean; ip: string }>(`/api/ip/${ip}/block`);
  }

  executeCommand(command: string) {
    return this.http.post<{ output: string }>('/api/command', { command });
  }

  fetchIncidents() {
    return this.http.get<Incident[]>('/api/incidents');
  }

  patchIncident(id: string, patch: { status?: IncidentStatus; assigned_to?: string | null }) {
    return this.http.patch<Incident>(`/api/incidents/${id}`, patch);
  }

  addIncidentNote(id: string, text: string, author = 'analyst1') {
    return this.http.post<IncidentNote>(`/api/incidents/${id}/notes`, { text, author });
  }

  updateIncidentTasks(id: string, completed_tasks: number[]) {
    return this.http.patch<{ completed_tasks: number[] }>(`/api/incidents/${id}/tasks`, { completed_tasks });
  }

  getIpCase(ip: string) {
    return this.http.get<{ case_id: string | null }>(`/api/ip/${ip}/case`);
  }

  fetchNetwork() {
    return this.http.get<{ nodes: NetworkNode[]; links: NetworkLink[] }>('/api/network');
  }

  runHunt(query: HuntQuery) {
    const params = Object.fromEntries(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== '' && v !== null)
    ) as Record<string, string>;
    return this.http.get<{ results: HuntResult[]; total: number }>('/api/hunt', { params });
  }

  getSavedHunts() {
    return this.http.get<SavedHunt[]>('/api/hunts');
  }

  saveHunt(name: string, query: HuntQuery, result_count: number) {
    return this.http.post<SavedHunt>('/api/hunts', { name, query, result_count });
  }

  deleteHunt(id: string) {
    return this.http.delete<{ ok: boolean }>(`/api/hunts/${id}`);
  }

  createCaseFromIp(ip: string) {
    return this.http.post<Incident & { existing: boolean }>('/api/incidents/from-ip', { ip });
  }

  setSimulation(active: boolean) {
    return this.http.post('/api/simulation', { active });
  }

  getRules() {
    return this.http.get<DetectionRule[]>('/api/rules');
  }

  createRule(rule: Partial<DetectionRule>) {
    return this.http.post<DetectionRule>('/api/rules', rule);
  }

  updateRule(id: string, patch: Partial<DetectionRule>) {
    return this.http.patch<DetectionRule>(`/api/rules/${id}`, patch);
  }

  deleteRule(id: string) {
    return this.http.delete<{ ok: boolean }>(`/api/rules/${id}`);
  }
}
