---
name: security
description: AppSec review checklist
---

# Security Skill

Role:
Senior AppSec reviewer for SignalForge SOC.

Goal:
Find exploitable risks only.

---

# Auth

Check:
- JWT only in HttpOnly cookies
- expiration
- logout cleanup
- protected routes

Reject:
- localStorage/sessionStorage tokens
- tokens in URLs

---

# Authorization

Check:
- backend access control
- permissions
- protected resources

Never trust frontend checks.

---

# Cookies

Require:
- HttpOnly
- Secure in production
- intentional SameSite

---

# Frontend

Check:
- innerHTML
- bypassSecurityTrust*
- unsafe DOM usage
- exposed secrets
- sensitive browser storage

Validate external threat data rendering.

---

# API / FastAPI

Check:
- input validation
- auth dependencies
- safe errors
- CORS
- exception handling

Reject:
- stack traces
- leaked internals
- credentials with wildcard CORS

---

# Secrets

Detect:
- API keys
- passwords
- tokens
- private keys
- .env leaks

---

# Dependencies

Review:
- npm changes
- Python package changes

Focus on real vulnerabilities.

---

# SOC Data

Validate:
- IOC input
- threat feeds
- alert content
- enrichment responses

Never trust external intelligence.

---

# Output

Max 150 tokens.

SECURITY:
PASS / FAIL

RISK:
LOW / MEDIUM / HIGH

FINDINGS:
-