# SignalForge Architecture Memory

## Product Overview

SignalForge is a Security Operations Center (SOC) platform.

The application helps analysts monitor, investigate and understand security threats.

Core goals:

- Real-time threat visibility
- Clear analyst workflow
- Fast incident understanding
- Security-first architecture

---

# Frontend Architecture

Framework:

Angular 19

Patterns:

- Standalone components
- Feature based architecture
- Signals for local UI state
- RxJS for async/event streams
- Services for data access
- Components for presentation and interaction

---

## State Management Rules

Use Signals for:

- UI state
- filters
- selections
- component state

Examples:

- selected alert
- active tab
- loading states


Use RxJS for:

- WebSocket streams
- HTTP flows
- async data pipelines
- event streams

Avoid:

- duplicated state
- unnecessary Subjects
- manual subscriptions without cleanup

---

# SOC Features

## Alerts

Security alerts represent suspicious activity.

Important fields:

- severity
- timestamp
- source
- status
- affected asset
- description


Architecture expectations:

- Alerts should support filtering
- Alerts should support investigation flow
- Real-time updates should not break UI state

---

## Threat Intelligence

Threat intelligence handles Indicators of Compromise.

IOC examples:

- IP address
- domain
- file hash
- malware indicators


Rules:

- Keep enrichment logic outside components
- Normalize external API responses
- Handle unavailable providers gracefully

---

## Dashboard

Dashboard purpose:

Provide quick security overview.

Rules:

Avoid:

- fake complexity
- meaningless charts
- duplicated calculations

Prefer:

- useful SOC metrics
- reusable visualization components

---

# Backend Architecture

Framework:

FastAPI

Structure:

Routers:
Handle HTTP layer only.

Services:
Contain business logic.

Models/Schemas:
Validate data.


Avoid:

- database access directly inside routes
- returning internal errors
- mixing auth logic everywhere

---

# Authentication

Authentication approach:

JWT stored using HttpOnly cookies.

Rules:

Never:

- store tokens in localStorage
- expose JWT to JavaScript
- leak authentication details


Always:

- validate users server-side
- protect sensitive routes
- use secure cookie configuration

---

# WebSocket Architecture

Purpose:

Real-time SOC updates.

Used for:

- live alerts
- event streaming
- monitoring data


Rules:

- handle disconnects
- avoid memory leaks
- cleanup subscriptions
- reconnect safely

---

# Engineering Priorities

Priority order:

1. Security
2. Correctness
3. Maintainability
4. Performance
5. Visual polish