# StoneOps Platform Blueprint (Production-Grade)

## 1) Executive Overview
StoneOps is an operations platform purpose-built for countertop templating and production operations. The platform is not a CRM and not a generic form app: it enforces operational gates, automates standard decisions, and routes exceptions. It reduces touches by preloading repeat plans, validating required data at intake and in-field closeout, running AI completeness checks, generating production packets, and preparing SPS-ready payloads.

Primary outcome targets:
- 40–60% reduction in repeated data entry.
- 30–50% reduction in processor/drafter touch time for standard jobs.
- >90% first-pass completeness at field submission.
- Faster same-day release rate from templating to production-ready.

## 2) Recommended System Architecture
- **Client Apps**
  - Web app (office users): intake, QA, approvals, planning, dashboards.
  - Tablet PWA (templaters): offline-first capture with sync queue.
- **API Layer (Flask REST)**
  - Job Intake Service
  - Scheduling/Dispatch Service
  - Field Submission Service
  - AI Completeness Service
  - Approval Service
  - SPS Staging Service
  - Dashboard Service
- **Rules + Decision Engine**
  - Builder/plan/material rules
  - Required-field gates
  - Exception routing logic
  - Auto-nesting eligibility (future-ready rules)
- **Data Layer (SQLite now, PostgreSQL in production)**
  - transactional tables (jobs, areas, approvals, submissions)
  - audit log tables
  - integration/staging tables for SPS
- **Integration Layer**
  - Raptor ingest endpoint / file parser
  - SPS mapper/export queue
  - Notification adapters (email/SMS)
  - object storage for drawings/photos/signatures

## 3) Core Modules + Connectivity
1. **Smart Job Intake** → creates validated Job + JobArea records.
2. **Repeat Plan Intelligence** → pulls prior plan history to suggest defaults.
3. **Scheduling/Dispatch** → assigns templater and route metadata.
4. **Field Templater Capture** → submits checklist/notes/signoff.
5. **AI Completeness Review** → scores and recommends: ready/correct/block.
6. **QA/Approval** → internal/external versioned approval decisions.
7. **Packet + SPS Staging** → structured production payload and export logs.
8. **Dashboards** → KPI rollups, exception trends, and accountability.

## 4) Database Schema (Implemented Core)
- `user` (roles, branches)
- `builder`
- `plan_template` (defaults_json + versioning)
- `job` (status-driven workflow spine)
- `job_area` (area-specific engineering details)
- `schedule` (dispatch, territory, dry-run)
- `template_submission` (field closeout)
- `ai_review` (score/missing/conflicts/recommendation)
- `approval` (audience + status + comments + version)
- `sps_export` (staging payload + push status)
- `audit_log` (actor, before/after, action)

## 5) User Flows (Departmental)
- **Sales/Order Entry**: create job → complete required fields → ready to schedule.
- **Scheduler**: assign templater + route + readiness confirmation.
- **Templater**: on-site checklist by area → capture photos/signoff → submit.
- **AI Engine**: auto-score submission → gate path.
- **Processor/QA**: review exceptions only; standard jobs pass through.
- **Approval Stakeholders**: approve/revise/reject with comments + version.
- **Planning/Production**: consume release-ready packet and SPS payload.
- **Leadership**: monitor cycle time, failure modes, branch comparisons.

## 6) AI Features + Rule Logic
### AI Completeness Engine
Inputs:
- job + area data
- latest field submission
- plan history comparison

Checks:
- missing required area-level fields
- photo completeness
- signature presence
- abnormal dimensions (e.g., overhang outliers)
- plan drift from prior jobs

Outputs:
- completeness score (0–100)
- missing item list
- conflict list
- recommendation: `ready_for_review` / `needs_correction` / `block`

### Repeat Plan Intelligence
- group by `builder + plan_number (+ community when needed)`
- find top-used sink/edge/splash/support patterns
- compare current submission against prior 5 jobs
- flag potential deviations requiring QA attention

## 7) MVP Scope
- Smart intake + required field gates
- Repeat-plan suggestions endpoint
- Scheduling/dispatch records
- Field submission with signature boolean/offline flag
- AI completeness scoring endpoint
- Approval status transitions
- SPS staging payload output
- KPI dashboard endpoint
- Full audit logs for operational accountability

## 8) Phased Roadmap
### Phase 1 (live foundation)
- Intake, required fields, repeat plan, field checklist, AI check, packet-ready data, dashboards.

### Phase 2 (control + integration)
- SPS push queue + retry handling
- richer approval routing and document markup refs
- processor QA workspace
- branch-level metrics and plan diff tooling

### Phase 3 (automation expansion)
- Raptor-driven drawing ingestion
- standard-job autopass to production-ready packet
- assisted nesting eligibility decision engine
- advanced operational analytics

### Phase 4 (optimization)
- partial auto nesting for approved standard jobs
- predictive issue detection from historical defects
- cross-branch optimization and benchmark alerts

## 9) Screen List (Spec)
1. Login + Role landing dashboard
2. Smart Job Entry (wizard)
3. Plan Suggestions/History side panel
4. Scheduling board + map routes
5. Templater tablet checklist (offline)
6. Field media upload + signoff page
7. AI completeness review screen
8. QA exception queue
9. Approval workspace (PDF + comments + version)
10. SPS staging/review/export screen
11. Packet release manager
12. KPI dashboards (ops + leadership + branch)
13. Admin rules editor (builder/plan/material)
14. Audit explorer

## 10) Suggested Tech Stack
- **Backend**: Python 3.11, Flask, SQLAlchemy, Celery/RQ for async jobs
- **DB**: PostgreSQL (prod), SQLite (dev)
- **Frontend**: React + TypeScript + TanStack Query + Material UI
- **Tablet**: PWA with IndexedDB sync queue + service worker
- **Storage**: S3-compatible object store
- **Auth**: OIDC/SAML + JWT; RBAC + optional ABAC rules
- **Observability**: OpenTelemetry + Prometheus/Grafana + Sentry
- **Messaging**: Twilio (SMS), SendGrid (email), webhook bus
- **AI**: rules-first deterministic checks + LLM-assisted anomaly summaries

## 11) Example End-to-End Workflow
1. AC creates Job `ATL-2026-00421` with 3 areas and material details.
2. System validates required fields and plan/builder rules; blocks missing sink specs.
3. Repeat-plan engine preloads edge/splash defaults from historical plan.
4. Scheduler assigns templater and dispatch window by territory.
5. Templater captures measurements, photos, signoff; syncs from tablet.
6. AI review scores 92.5, no missing items, recommendation `ready_for_review`.
7. QA spot-checks only (standard job) and routes to internal approval.
8. Approval granted; job moves to `ready_for_production`.
9. SPS staging payload generated and queued for push.
10. Production packet released with revision + approval history.

## 12) Risks, Assumptions, Dependencies
### Risks
- inconsistent plan naming reduces repeat intelligence quality
- poor field network coverage without robust offline sync
- SPS schema drift causing mapping breaks
- Raptor export inconsistency by branch or device version

### Assumptions
- standardized sink/appliance/edge libraries are maintained centrally
- branch territories and schedule windows are defined in admin config
- role ownership and SLA definitions are provided by operations leadership

### Dependencies
- SPS integration specs and access credentials
- Raptor data contract and sample files/API
- notification providers and compliance setup (SMS opt-in)
- file storage lifecycle/security policy

## 13) Next Build Steps
1. Add JWT auth + RBAC enforcement middleware.
2. Build React office UI and tablet PWA views against current API.
3. Add async worker for notifications, packet generation, SPS retries.
4. Add document/media storage integration.
5. Implement production PostgreSQL migration + indexing.
6. Build automated tests for rules, AI review, and status transitions.
7. Run branch pilot with instrumentation for touch-time reduction metrics.
