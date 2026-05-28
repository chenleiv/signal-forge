export type ThreatLevel = 'critical' | 'high' | 'medium' | 'low';
export type AttackType = 'SQLi' | 'DDoS' | 'BruteForce' | 'PortScan' | 'Malware';

export interface ThreatEvent {
  ip: string;
  score: number;
  threat_level: ThreatLevel;
  attack_type: AttackType;
  timestamp: string;
  region: string;
}

export interface ThreatStats {
  severity_counts: Record<ThreatLevel, number>;
  attack_types: Record<AttackType, number>;
  events_per_min: { minute: string; count: number }[];
  top_ips: { ip: string; count: number; score: number }[];
}

export interface IpHistory {
  ip: string;
  score: number;
  threat_level: ThreatLevel;
  events: ThreatEvent[];
  regions: string[];
  mitre_tags: string[];
}

export type IncidentStatus = 'open' | 'investigating' | 'contained' | 'closed';

export interface Incident {
  id: string;
  title: string;
  severity: ThreatLevel;
  status: IncidentStatus;
  attack_type: AttackType;
  source_region: string;
  event_count: number;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
  mitre_tags: string[];
}
