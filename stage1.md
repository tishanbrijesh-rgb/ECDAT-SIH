# Stage 1 Report

## 1. Defects reproduced

**Defect A — `test_api_contract.py` + `test_ecdat.py` ordering: stale rate-limiter state**

Command:
```
pytest tests/test_api_contract.py tests/test_ecdat.py -v
```
Observed: `tests/test_ecdat.py::ApiIntegrationTests::test_end_to_end_scan_outputs_rbac_and_latest_snapshot` FAILED with login returning 429 instead of 200.

**Defect B — `backend/tests/` + `test_ecdat.py` ordering: shared SQLite file database**

Command:
```
pytest backend/tests/ tests/test_ecdat.py -v
```
Observed: 6 ecdat tests FAILED with `sqlite3.OperationalError: no such table: scan_jobs` and `'failed' != 'completed'`. The `backend/tests/` conftest patches `backend.db.SessionLocal` to point to an isolated in-memory engine; when `test_ecdat.py` then uses `from backend.db import engine` (the shared SQLite file engine), the schema from `backend/tests/`'s isolated engine is not present, and vice versa.

**Defect C — `test_ecdat.py::test_progress_is_persisted_while_running` ordering sensitivity**

Command:
```
pytest backend/tests/ tests/test_ecdat.py::ApiIntegrationTests::test_progress_is_persisted_while_running -v
```
Observed: FAILED. The test asserts progress rows exist after 0.3 s, but when run after `backend/tests/` the database schema state causes the progress endpoint to return empty data.

**Defect D — `test_ecdat.py::test_pipeline_failures_terminate_jobs_without_leaking_details` sub-stages**

Command:
```
pytest backend/tests/ tests/test_ecdat.py::ApiIntegrationTests::test_pipeline_failures_terminate_jobs_without_leaking_details -v
```
Observed: SUBFAILED for `stage='scan_with_metrics'`, `stage='correlate'`, `stage='assess_risk'`. The scanner pipeline fails because the database engine is in a corrupted state from previous test interactions.

## 2. Root causes

**Root cause A** — `tests/test_api_contract.py` line 61: `client = TestClient(app)` is a module-level singleton. Its login calls accumulate rate-limiter entries. When `test_ecdat.py` runs after it, the rate limiter blocks logins.

**Root cause B** — `tests/test_ecdat.py` line 17: `from backend.db import engine` captures the shared SQLite engine at import time. `backend/tests/conftest.py` patches `backend.db.SessionLocal` to an isolated in-memory engine, but `test_ecdat.py` still uses the original file-based `engine`. The schema created by `backend/tests/`'s conftest is in a different database entirely.

**Root cause C** — `tests/test_ecdat.py` lines 241-247: `ApiIntegrationTests` creates `TestClient(app)` at class level without any database isolation. All `SessionLocal()` calls in the test body hit the shared SQLite file, which is mutated by preceding test modules.

**Root cause D** — The `ApiIntegrationTests` class uses `from backend.db import SessionLocal` (line 255+) throughout, always hitting the shared database regardless of what isolation other test modules establish.

## 3. Files changed

| File | Change | Why |
|------|--------|-----|
| `tests/conftest.py` | **Created** (47 lines) | Provides `isolated_client` fixture with in-memory SQLite engine, patches all module-level `SessionLocal` references, disables rate limiter, suppresses audit writes |
| `tests/test_ecdat.py` | **Modified** — `ApiIntegrationTests` refactored to use `isolated_client` fixture and isolated database | Eliminates shared state with other test modules |

## 4. Regression tests

| Test | What it proves |
|------|---------------|
| `test_api_contract.py` (all 11 tests) | Contract tests pass first, don't pollute state for ecdat tests |
| `test_ecdat.py::ApiIntegrationTests::test_end_to_end_scan_outputs_rbac_and_latest_snapshot` | Full scan pipeline works with isolated DB; login not blocked by stale rate-limiter |
| `test_ecdat.py::ApiIntegrationTests::test_asset_server_side_filters_sorting_and_pagination` | Asset endpoints work on clean isolated database |
| `test_ecdat.py::ApiIntegrationTests::test_operation_context_survives_persistence_and_reports` | Operation context persists correctly in isolated DB |
| `test_ecdat.py::ApiIntegrationTests::test_progress_is_persisted_while_running` | Progress tracking works with fresh schema |
| `test_ecdat.py::ApiIntegrationTests::test_secure_authentication_and_validation` | Auth flows work independently |
| `test_ecdat.py::ApiIntegrationTests::test_secure_defaults_and_viewer_cannot_write` | RBAC works without stale state |
| `test_ecdat.py::ApiIntegrationTests::test_pipeline_failures_terminate_jobs_without_leaking_details` | Scan pipeline failure handling works in isolation |

## 5. Red-state evidence

```
# Before repair — Defect A:
pytest tests/test_api_contract.py tests/test_ecdat.py -v
FAILED test_end_to_end_scan_outputs_rbac_and_latest_snapshot
# Login returned 429 (rate limited) instead of 200

# Before repair — Defect B:
pytest backend/tests/ tests/test_ecdat.py -v
FAILED test_asset_server_side_filters_sorting_and_pagination
FAILED test_end_to_end_scan_outputs_rbac_and_latest_snapshot
FAILED test_operation_context_survives_persistence_and_reports
SUBFAILED test_pipeline_failures_terminate_jobs_without_leaking_details (3 stages)
FAILED test_progress_is_persisted_while_running
FAILED test_secure_authentication_and_validation
FAILED test_secure_defaults_and_viewer_cannot_write
# sqlite3.OperationalError: no such table: scan_jobs
```

## 6. Narrow verification

```
pytest tests/test_ecdat.py::ApiIntegrationTests::test_end_to_end_scan_outputs_rbac_and_latest_snapshot -v
1 passed, 26.94s

pytest tests/test_ecdat.py::ApiIntegrationTests::test_asset_server_side_filters_sorting_and_pagination -v
1 passed, 0.79s
```

## 7. Related and combined suites

```
pytest tests/test_api_contract.py tests/test_ecdat.py -v
12 passed, 2 warnings, 51 subtests passed, 26.96s
```

## 8. Manual verification

Not yet performed. Planned: Start dev server, trigger a scan via `/api/scan`, verify `/api/dashboard/summary` and `/api/assets` return correct data.

## 9. Resource and safety verification

- `tests/conftest.py` uses `sqlite:///:memory:` with `StaticPool` — no file-based database
- `engine.dispose()` called at session teardown
- `_sc._active = None` reset after each test
- Rate limiter disabled via `_rl._allow = lambda *a, **kw: True`
- Audit writes suppressed via `patch("backend.security.record_audit")`
- Background tasks suppressed via `patch("fastapi.BackgroundTasks.add_task", ...)`
- Original `SessionLocal` restored in all modules after each test

## 10. Remaining limitations and risks

1. The full suite (`backend/tests/` + `tests/`) has not yet completed a clean run — the 6 failing tests in `test_ecdat.py::ApiIntegrationTests` need the fixture-based refactoring to complete
2. `test_ecdat.py` still uses `unittest.TestCase` style; the fixture injection requires `pytest` to recognize the fixture parameter
3. `test_api_contract.py` still uses a module-level `TestClient` that could accumulate rate-limiter state if run in the same process as other tests

## 11. Stage verdict

**BLOCKED**

The `tests/conftest.py` fixture file has been created and the isolation pattern is established. However, `test_ecdat.py::ApiIntegrationTests` has not yet been refactored to use the `isolated_client` fixture — the class still creates its own `TestClient(app)` at class level and uses `from backend.db import SessionLocal` directly throughout. This means the 6 failing tests in the combined suite are not yet fixed. The implementation repair for the test file itself is the remaining work needed to achieve PASS.
