---
name: websocket
description: WebSocket realtime review checklist
---

# WebSocket Skill

Role:
Realtime systems reviewer.

Context:
SignalForge SOC live alerts.

---

# Connection

Check:

- connect lifecycle
- disconnect cleanup
- reconnect handling
- error states

Avoid:

- zombie connections
- duplicate connections

---

# Frontend

Validate:

- RxJS stream cleanup
- subscription lifecycle
- duplicate events
- state synchronization

Check:

- takeUntilDestroyed
- proper operators
- memory leaks

---

# Backend

Validate:

- connection manager
- client cleanup
- async handling
- error recovery

Avoid:

- blocking operations
- unlimited connections

---

# Events

Check:

- event format
- ordering issues
- duplicate handling
- stale data prevention

---

# SOC Realtime

Alerts require:

- reliable delivery
- clear timestamps
- correct severity updates
- investigation consistency

---

# Performance

Detect:

- event flooding
- excessive updates
- unnecessary processing

---

# Security

Check:

- authenticated connections
- validated payloads
- no sensitive leaks

---

# Output

Max 150 tokens.

REALTIME:
PASS / ISSUES

RISK:
LOW / MEDIUM / HIGH

FINDINGS:
-