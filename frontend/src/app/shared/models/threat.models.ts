export type ThreatLevel = 'critical' | 'high' | 'medium' | 'low';
export type AttackType = 'SQLi' | 'DDoS' | 'BruteForce' | 'PortScan' | 'Malware';

export interface ThreatEvent {
  ip: string;
  score: number;
  threat_level: ThreatLevel;
  attack_type: AttackType;
  timestamp: string;
  region: string;
  lat?: number;
  lng?: number;
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
  abuse_confidence?: number;
  country_code?: string;
  isp?: string;
  total_reports?: number;
}

export interface IpGeo {
  country: string;
  country_code: string;
  city: string;
  org: string;
  asn: string;
  timezone: string;
}

export interface RelatedIp {
  ip: string;
  shared_attacks: string[];
  score: number;
  threat_level: ThreatLevel;
  event_count: number;
}

export interface NetworkNode {
  id: string;
  type: 'ip' | 'attack';
  score?: number;
  threat_level?: ThreatLevel;
  event_count?: number;
}

export interface NetworkLink {
  source: string;
  target: string;
  value: number;
}

export interface HuntQuery {
  ip?: string;
  attack_type?: string;
  region?: string;
  min_score?: number;
  max_score?: number;
}

export interface SavedHunt {
  id: string;
  name: string;
  query: HuntQuery;
  created_at: string;
  result_count: number;
}

export type HuntResult = ThreatEvent;

export interface RuleCondition {
  field: 'score' | 'attack_type' | 'region' | 'ip';
  operator: '>' | '<' | '=' | 'contains';
  value: string | number;
}

export type RuleAction = 'alert' | 'incident' | 'block';

export interface DetectionRule {
  id: string;
  name: string;
  enabled: boolean;
  conditions: RuleCondition[];
  logic: 'AND' | 'OR';
  actions: RuleAction[];
  created_at: string;
  match_count: number;
}

export type IncidentStatus = 'open' | 'investigating' | 'contained' | 'closed';

export interface IncidentNote {
  author: string;
  text: string;
  at: string;
}

export interface Incident {
  id: string;
  title: string;
  severity: ThreatLevel;
  status: IncidentStatus;
  attack_type: AttackType;
  source_ip?: string;
  source_region: string;
  event_count: number;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
  mitre_tags: string[];
  notes: IncidentNote[];
  completed_tasks: number[];
}
