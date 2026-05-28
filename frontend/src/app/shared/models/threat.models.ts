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
