from __future__ import annotations

COUNTRY_NAMES: dict[str, str] = {
    "US": "United States", "RU": "Russia", "CN": "China",
    "DE": "Germany", "GB": "United Kingdom", "FR": "France",
    "NL": "Netherlands", "IL": "Israel", "BR": "Brazil",
    "JP": "Japan", "KR": "South Korea", "IN": "India",
    "CA": "Canada", "AU": "Australia", "SE": "Sweden",
    "RO": "Romania", "UA": "Ukraine", "IS": "Iceland",
    "SG": "Singapore", "TR": "Turkey", "PL": "Poland",
    "IR": "Iran", "KP": "North Korea", "NG": "Nigeria",
}

GEO_DATA: dict[str, dict] = {
    "185.220.101.47": {"country": "Germany",     "country_code": "DE", "city": "Frankfurt", "org": "Tor Exit Relay",       "asn": "AS24940", "timezone": "Europe/Berlin"},
    "45.33.32.156":   {"country": "USA",          "country_code": "US", "city": "Atlanta",   "org": "Akamai Technologies",  "asn": "AS63949", "timezone": "America/New_York"},
    "104.21.33.14":   {"country": "USA",          "country_code": "US", "city": "San Jose",  "org": "Cloudflare Inc",       "asn": "AS13335", "timezone": "America/Los_Angeles"},
    "77.88.8.8":      {"country": "Russia",       "country_code": "RU", "city": "Moscow",    "org": "Yandex LLC",           "asn": "AS13238", "timezone": "Europe/Moscow"},
    "80.82.77.139":   {"country": "Netherlands",  "country_code": "NL", "city": "Amsterdam", "org": "Shodan Monitoring",    "asn": "AS60557", "timezone": "Europe/Amsterdam"},
    "5.188.206.14":   {"country": "Russia",       "country_code": "RU", "city": "Moscow",    "org": "Inferno Solutions",    "asn": "AS57523", "timezone": "Europe/Moscow"},
    "194.165.16.11":  {"country": "Iceland",      "country_code": "IS", "city": "Reykjavik", "org": "1984 ehf",             "asn": "AS44925", "timezone": "Atlantic/Reykjavik"},
    "91.108.4.1":     {"country": "Netherlands",  "country_code": "NL", "city": "Amsterdam", "org": "Telegram Messenger",   "asn": "AS62041", "timezone": "Europe/Amsterdam"},
    "185.159.82.45":  {"country": "Romania",      "country_code": "RO", "city": "Bucharest", "org": "M247 Europe SRL",      "asn": "AS49327", "timezone": "Europe/Bucharest"},
    "51.15.193.47":   {"country": "France",       "country_code": "FR", "city": "Paris",     "org": "Online S.A.S.",        "asn": "AS12876", "timezone": "Europe/Paris"},
    "167.99.247.3":   {"country": "Germany",      "country_code": "DE", "city": "Frankfurt", "org": "DigitalOcean LLC",     "asn": "AS14061", "timezone": "Europe/Berlin"},
    "64.225.32.100":  {"country": "USA",          "country_code": "US", "city": "New York",  "org": "DigitalOcean LLC",     "asn": "AS14061", "timezone": "America/New_York"},
}

ATTACK_TYPES = ["SQLi", "DDoS", "BruteForce", "PortScan", "Malware"]
REGIONS = ["US", "EU", "RU", "CN", "IL", "BR"]

MITRE_MAP: dict[str, list[str]] = {
    "SQLi":       ["T1190", "T1059"],
    "DDoS":       ["T1498", "T1499"],
    "BruteForce": ["T1110"],
    "PortScan":   ["T1046"],
    "Malware":    ["T1059", "T1204"],
    "RepeatedIP": ["T1078", "T1110"],
    "Escalation": ["T1071", "T1496"],
}

INCIDENT_TITLES = {
    "SQLi":       "SQL Injection campaign detected",
    "DDoS":       "Distributed Denial of Service attack",
    "BruteForce": "Brute Force authentication attack",
    "PortScan":   "Reconnaissance port scan detected",
    "Malware":    "Malware execution detected",
    "RepeatedIP": "Repeated attacker — behavioral spike detected",
    "Escalation": "Threat score escalation — attacker intensifying",
}

ANALYSTS = ["Alice Chen", "Bob Martinez", "Sarah Kim", "James Liu", None]

_SEVERITY_BANDS = [
    ("low",       1,  39, 0.15),
    ("medium",   40,  59, 0.30),
    ("high",     60,  79, 0.35),
    ("critical", 80, 100, 0.20),
]

_SQLI_PAYLOADS    = ["' OR 1=1--", "' UNION SELECT null,null--", "'; DROP TABLE users--", "' AND SLEEP(5)--", "admin'--", "' OR 'x'='x"]
_MALWARE_FAMILIES = ["Emotet", "Mirai", "BlackMatter", "Cobalt Strike", "AsyncRAT", "Raccoon"]
_SERVICES         = ["SSH", "RDP", "FTP", "SMTP", "HTTP", "VNC"]
_PROTOCOLS        = ["UDP", "TCP", "ICMP"]
_SCAN_TYPES       = ["SYN", "ACK", "XMAS", "NULL", "FIN"]
_ENDPOINTS        = ["/api/login", "/admin", "/wp-admin", "/api/users", "/graphql", "/.env"]
