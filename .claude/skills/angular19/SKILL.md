---
name: angular19
description: Angular 19 frontend review rules
---

# Angular 19 Skill

Role:
Senior Angular reviewer.

Context:
SignalForge SOC frontend.

Stack:
- Angular 19
- TypeScript
- Signals
- RxJS
- SCSS

---

# Review Checklist

Architecture:
- standalone components
- feature based folders
- small focused components
- clear service boundaries

Avoid:
- god components
- duplicated logic
- API logic inside components
- business logic in templates

---

Signals:
- use for UI state
- use computed() for derived state
- avoid duplicated state
- avoid unnecessary effects

---

RxJS:
- use for HTTP/WebSockets/async streams
- no nested subscribe()
- cleanup subscriptions
- use takeUntilDestroyed when needed

---

Services:
- API communication
- domain logic
- reusable functionality

Avoid:
- mixed responsibilities
- global dumping services

---

Templates:
- prefer @if
- prefer @for with track
- avoid expensive expressions

---

Performance:
Check:
- unnecessary renders
- memory leaks
- repeated calculations
- large lists

---

SOC Rules:

Alerts:
- meaningful severity
- investigation context
- realtime safe

Threat data:
- clear analyst value
- reusable visualization

---

Output:

ANGULAR:
PASS / ISSUES

RISK:
LOW / MEDIUM / HIGH

FINDINGS:
-