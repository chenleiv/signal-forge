"""Demo mode's source IP addresses: simulated only, never a real third party.

Every address is in one of the three IPv4 documentation ranges (RFC 5737),
which are never routed on the internet, so no real host can be shown as an
attacker. Each one gets a fixed score and simulated geolocation: a real city
(so the map spreads out), the organisation "Simulated network" and an ASN from
the documentation range AS64496-AS64511 (RFC 5398).

The pool is generated once from a fixed seed, so it is the same on every start.
"""
from __future__ import annotations

import ipaddress
import random

from constants import COUNTRY_NAMES

SIMULATED_NETWORKS = tuple(
    ipaddress.ip_network(net) for net in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)
IPS_PER_NETWORK = 12
SIMULATED_ORG = "Simulated network"
_FIRST_DOC_ASN, _LAST_DOC_ASN = 64496, 64511
_SEED = 5737

# (country code, city, latitude, longitude, timezone)
_CITIES: tuple[tuple[str, str, float, float, str], ...] = (
    ("US", "Chicago",   41.88,  -87.63, "America/Chicago"),
    ("DE", "Frankfurt", 50.11,    8.68, "Europe/Berlin"),
    ("NL", "Amsterdam", 52.37,    4.90, "Europe/Amsterdam"),
    ("RU", "Moscow",    55.76,   37.62, "Europe/Moscow"),
    ("CN", "Beijing",   39.90,  116.40, "Asia/Shanghai"),
    ("BR", "Sao Paulo", -23.55, -46.63, "America/Sao_Paulo"),
    ("RO", "Bucharest", 44.43,   26.10, "Europe/Bucharest"),
    ("SG", "Singapore",  1.35,  103.82, "Asia/Singapore"),
    ("IN", "Mumbai",    19.08,   72.88, "Asia/Kolkata"),
    ("KR", "Seoul",     37.57,  126.98, "Asia/Seoul"),
    ("UA", "Kyiv",      50.45,   30.52, "Europe/Kyiv"),
    ("NG", "Lagos",      6.52,    3.38, "Africa/Lagos"),
)


def _build() -> tuple[dict[str, int], dict[str, dict]]:
    rng = random.Random(_SEED)
    scores: dict[str, int] = {}
    geo: dict[str, dict] = {}
    for network in SIMULATED_NETWORKS:
        hosts = list(network.hosts())
        for host in sorted(rng.sample(hosts, IPS_PER_NETWORK)):
            ip = str(host)
            scores[ip] = rng.randint(40, 100)
            code, city, lat, lng, tz = rng.choice(_CITIES)
            geo[ip] = {
                "country": COUNTRY_NAMES.get(code, code),
                "country_code": code,
                "city": city,
                "org": SIMULATED_ORG,
                "asn": f"AS{rng.randint(_FIRST_DOC_ASN, _LAST_DOC_ASN)}",
                "timezone": tz,
                "lat": lat,
                "lng": lng,
            }
    return scores, geo


SIMULATED_IPS, SIMULATED_GEO = _build()


def is_simulated_ip(ip: object) -> bool:
    """True only for an address of the simulated pool."""
    return isinstance(ip, str) and ip in SIMULATED_IPS
