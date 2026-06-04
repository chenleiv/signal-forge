# SignalForge Coding Conventions

This document defines engineering conventions used across the project.

All agents must follow these rules.

---

# General Principles

Optimize for:

1. Readability
2. Maintainability
3. Security
4. Simplicity

Code should look like it belongs in a professional engineering team.

Avoid:

- clever solutions
- unnecessary abstractions
- premature optimization
- large rewrites

Prefer:

- small focused changes
- explicit naming
- predictable patterns

---

# TypeScript Rules

Always:

- use strict typing
- create clear interfaces
- prefer readonly where useful
- handle nullable values safely

Avoid:

- any
- type assertions without reason
- duplicated types
- magic strings

Examples:

Prefer:

type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'

over:

severity: string

---

# Angular Rules

SignalForge uses Angular 19.

Prefer:

- standalone components
- feature folders
- dependency injection with inject()
- signals for local state
- computed() for derived state
- modern template syntax


Use:

@if

instead of:

*ngIf


Use:

@for

instead of:

*ngFor


Components should:

- handle UI logic
- delegate business logic
- stay small


Avoid:

- API calls directly in components
- large component files
- duplicated state
- nested subscriptions

---

# Signals

Use signals for:

- UI state
- selected items
- filters
- loading states


Example:

selectedAlert = signal<Alert | null>(null)


Use computed for:

- derived values
- filtered lists


Avoid:

- using effects as event handlers
- mutating signal values directly
- storing server streams as signals unnecessarily

---

# RxJS

Use RxJS for:

- HTTP streams
- WebSocket events
- async flows


Rules:

Always:

- prevent memory leaks
- unsubscribe safely
- use takeUntilDestroyed when needed


Avoid:

- nested subscribe()
- unnecessary Subjects
- manual state syncing

---

# SCSS

Rules:

Prefer:

- component scoped styles
- readable class names
- reusable variables


Avoid:

- global overrides
- deeply nested selectors
- inline styles

---

# Backend Python Rules

FastAPI conventions:

Routers:

Only handle:

- HTTP requests
- validation
- responses


Services:

Handle:

- business logic
- integrations
- processing


Avoid:

- database logic inside routes
- authentication duplication

---

# API Rules

Endpoints should:

- have clear naming
- validate input
- return predictable responses


Errors should:

- be handled explicitly
- not expose internal details

---

# Security Rules

Never commit:

- API keys
- passwords
- tokens
- secrets


Authentication:

JWT rules:

- HttpOnly cookies only
- no localStorage
- no exposing tokens to frontend


Frontend security:

Always check:

- XSS risks
- unsafe HTML
- exposed environment variables

---

# Git Rules

Commits should:

- describe intent
- keep related changes together


Before commit:

Run:

- architecture review
- security review
- quality validation

---

# Claude Behavior

When modifying code:

First:
- understand existing patterns
- inspect related files

Then:
- propose solution
- make minimal changes

Never:

- rewrite working systems
- change architecture without approval
- remove security logic
- ignore existing conventions