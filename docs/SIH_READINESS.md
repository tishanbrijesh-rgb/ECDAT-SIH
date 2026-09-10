# SIH readiness checklist

Updated: 2026-09-10

```mermaid
flowchart LR
    Code[Code gates] --> Demo[Local demo]
    Demo --> Browser[Browser checks]
    Browser --> CI[Remote CI]
    CI --> Ready[Presentation ready]
```

## Implemented

- [x] Multi-source cryptographic discovery
- [x] Evidence normalization and logical correlation
- [x] Confidence, conflicts, measured coverage and blind spots
- [x] Mosca-style risk and usage-aware PQC recommendations
- [x] Searchable inventory and evidence detail
- [x] CBOM, risk report, evidence graph and controlled evaluation
- [x] Signed demo sessions, RBAC and append-only audit events
- [x] Configurable CORS and allowed scan roots
- [x] SQLite local mode and PostgreSQL Compose mode
- [x] Automated API, scanner and risk tests
- [x] TypeScript compilation, formatting, production build and dependency audit
- [x] GitHub Actions continuous integration
- [x] Request IDs, JSON logging, endpoint rate limits and stale-job recovery
- [x] Database scan leases and authenticated live-progress events
- [x] Architecture, threat model and five-minute demonstration script

## Must be verified on the presentation machine

- [x] Docker Desktop is installed and disposable Compose verification succeeds
- [x] Ports 18080 and 18081 were available for isolated verification; the regular
  demo still requires ports 3000, 8000 and 5432 to be free at presentation time
- [x] The `/test-repo` scan completes through the Docker/PostgreSQL deployment
- [ ] Browser downloads for the risk report are allowed
- [ ] A screen recording and screenshots are available as offline fallback
- [x] The verified branch is pushed to the team Git remote
- [ ] Confirm the latest GitHub Actions run is green before the presentation
- [x] Alembic migrations (0001–0004) verified on clean and populated databases
- [x] Scan failures persist via relational `scan_failures` table

## Deliberately out of SIH prototype scope

- Production SSO and multi-tenancy
- Isolated distributed scanner workers
- Binary, runtime, cloud KMS, network and HSM collectors
- Enterprise-scale benchmark corpus
- Kubernetes, high availability and disaster recovery
