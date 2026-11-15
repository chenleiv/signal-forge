export type ThreatLevel = 'critical' | 'high' | 'medium' | 'low';
export type AttackType = 'SQLi' | 'DDoS' | 'BruteForce' | 'PortScan' | 'Malware' | 'RepeatedIP' | 'Escalation';

export const ATTACK_TYPES = ['SQLi', 'DDoS', 'BruteForce', 'PortScan', 'Malware'] as const;
export const REGIONS      = ['US', 'EU', 'RU', 'CN', 'IL', 'BR'] as const;

export const DETECTION_SOURCE_LABELS: Record<string, string> = {
  sigma_rule:           'Sigma Rule',
  behavioral_detection: 'Behavioral',
  threat_intelligence:  'Threat Intel',
  correlation_engine:   'Correlation',
  yara_detection:       'YARA',
};

// Severity colors are theme CSS variables (see src/styles.scss), so they follow
// the light and dark theme. Use them in style bindings or D3 .style(), never in
// SVG presentation attributes, which cannot resolve var().
// SEVERITY_COLORS is the fill tier, for dots, stripes and strokes (3:1).
// SEVERITY_TEXT_COLORS is the text tier, for readable labels (4.5:1).
export const SEVERITY_COLORS: Record<string, string> = {
  critical: 'var(--c-sev-critical-fill)',
  high:     'var(--c-sev-high-fill)',
  medium:   'var(--c-sev-medium-fill)',
  low:      'var(--c-sev-low-fill)',
};

export const SEVERITY_TEXT_COLORS: Record<string, string> = {
  critical: 'var(--c-sev-critical)',
  high:     'var(--c-sev-high)',
  medium:   'var(--c-sev-medium)',
  low:      'var(--c-sev-low)',
};

/** A translucent tint of a color, including a var() color: `pct` is 0 to 100. */
export function tint(color: string, pct: number): string {
  return `color-mix(in srgb, ${color} ${pct}%, transparent)`;
}

function scoreToLevel(score: number): ThreatLevel {
  if (score >= 80) return 'critical';
  if (score >= 60) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
}

/** Fill tier color for a risk score, for gauges and bars. */
export function scoreToColor(score: number): string {
  return SEVERITY_COLORS[scoreToLevel(score)];
}

/** Text tier color for a risk score, for labels. */
export function scoreToTextColor(score: number): string {
  return SEVERITY_TEXT_COLORS[scoreToLevel(score)];
}

export interface ThreatEvent {
  ip: string;
  score: number;
  threat_level: ThreatLevel;
  attack_type: AttackType;
  timestamp: string;
  region: string;
  lat?: number;
  lng?: number;
  // DDoS
  packet_rate?: number;
  duration_sec?: number;
  protocol?: string;
  // SQLi
  payload?: string;
  target_endpoint?: string;
  // BruteForce
  attempts?: number;
  username?: string;
  service?: string;
  // PortScan
  ports_scanned?: number[];
  scan_type?: string;
  // Malware
  family?: string;
  hash?: string;
  c2_domain?: string;
  // Behavioral
  dominant_attack?: string;
  event_count_10m?: number;
  overall_avg?: number;
  recent_avg?: number;
}

export interface ThreatStats {
  severity_counts: Record<ThreatLevel, number>;
  attack_types: Partial<Record<AttackType, number>>;
  events_per_min: { minute: string; count: number }[];
  top_ips: { ip: string; count: number; score: number; threat_level: ThreatLevel }[];
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

export type UserRole = 'admin' | 'manager' | 'analyst';

/** A user as listed by GET /api/users (never includes credentials). */
export interface UserSummary {
  username: string;
  display_name: string;
  role: UserRole;
}

/** GET /api/users/directory: every name ever used, including deleted users. */
export interface UserDirectoryEntry {
  username: string;
  display_name: string;
  deleted: boolean;
}

export interface NewUser {
  username: string;
  display_name: string;
  role: UserRole;
  password: string;
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

export interface OtxPulse {
  name: string;
  tags: string[];
  author: string;
  created: string;
}

export interface OtxData {
  pulse_count: number;
  reputation: number;
  pulses: OtxPulse[];
  malware_families: string[];
}

export type AlertStatus = 'new' | 'acknowledged' | 'dismissed';
export type AlertSource = 'behavioral' | 'rule';
export type DetectionSource =
  | 'sigma_rule'
  | 'behavioral_detection'
  | 'threat_intelligence'
  | 'correlation_engine'
  | 'yara_detection';

export type AlertTimelineEntryType = 'detection' | 'attempt' | 'behavior' | 'alert' | 'response';

export interface AlertTimelineEntry {
  event: string;
  description: string;
  type: AlertTimelineEntryType;
  at: string;
}

export interface AlertSummaryMetrics {
  active_threats: number;
  critical_alerts: number;
  mttr_min: number;
  top_attack_type: string;
  blocked_indicators: number;
}

export interface ThreatAlert {
  id: string;
  source: AlertSource;
  detection_source: DetectionSource;
  type: string;
  severity: ThreatLevel;
  ip: string | null;
  country: string;
  country_code: string;
  affected_asset: string;
  mitre_technique: string;
  confidence_score: number;
  risk_score: number;
  message: string;
  status: AlertStatus;
  created_at: string;
  acknowledged_at: string | null;
  event_timeline: AlertTimelineEntry[];
}
