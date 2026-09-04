# ECDAT — Enterprise Cryptographic Discovery & Analysis Tool

ECDAT is the SIH26164 privacy-first cryptographic inventory and discovery-assurance prototype. It correlates explainable evidence from source structure, auditable multi-language rules, dependencies, and X.509 certificates; measures confidence and coverage separately; exposes conflicts and blind spots; and produces context-aware PQC migration priorities.

## One-command demo

```bash
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000), select **New scan**, keep `/test-repo`, and start discovery. API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

Without Docker, run the backend with SQLite and the dashboard separately:

Install the Python runtime and test dependencies from the repository root first:

```powershell
python -m pip install -r req.txt
```

```powershell
$env:DATABASE_URL="sqlite:///./ecdat_local.db"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
cd dashboard
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

## Tests and continuous integration

Run the dependency-free Python unit/API integration suite and the production dashboard build:

```powershell
python -m unittest discover -s tests -v
cd dashboard
npm ci
npm run build
```

The integration suite scans the controlled repository twice and verifies discovery metrics, correlation conflicts, risk recalculation, CBOM, reports, evidence graph, evaluation, audit history, role boundaries, and latest-scan isolation. GitHub Actions runs the same checks on every push and pull request.

On Windows, run the complete release gate with:

```powershell
.\scripts\verify_release.ps1
```

## SIH presentation pack

- [Architecture](docs/ARCHITECTURE.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Five-minute demonstration](docs/DEMO_SCRIPT.md)
- [Readiness checklist](docs/SIH_READINESS.md)

The local demo accepts signed sessions from `POST /api/auth/login`. Documented usernames are `admin`, `analyst`, `auditor`, and `viewer`; the default offline-demo password is `ecdat-demo`. Change `ECDAT_DEMO_PASSWORD` and `ECDAT_TOKEN_SECRET` outside the controlled demonstration. The compatibility role header can be disabled with `ECDAT_ALLOW_ROLE_HEADER=false`.

## Eight-layer architecture

1. **Collection** — repositories, source files, manifests, and certificates.
2. **Detection** — Python AST, independent JSON rules, dependency mapping, and X.509 parsing.
3. **Normalization** — a common cryptographic-asset and evidence model.
4. **Correlation** — component-level logical assets and evidence relationships.
5. **Discovery Assurance** — confidence, measured coverage, operation conflicts, and blind spots.
6. **Risk** — quantum exposure, Mosca planning window, sensitivity, criticality, exposure, and migration effort.
7. **Recommendation** — usage-aware ML-KEM, ML-DSA, SLH-DSA, symmetric, or hybrid guidance.
8. **Presentation** — assurance dashboard, inventory, evidence detail, CBOM, reports, graph, evaluation, and APIs.

| Layer | Technology |
|---|---|
| Scanner | Python AST, auditable regex rules, `cryptography` |
| API | FastAPI and Pydantic |
| Persistence | SQLAlchemy and PostgreSQL 16; SQLite for local demo |
| Dashboard | React 18, TypeScript, Vite, Recharts |
| Runtime | Docker Compose |

## Discovery Assurance

- **Confidence** measures the strength and agreement of independent evidence for one finding.
- **Coverage** is measured from successfully scanned supported files, never inferred from confidence.
- **Conflicts** require incompatible algorithms in the same operation and category; a file legitimately using AES, RSA, and SHA is not a conflict.
- **Blind spots** state which enterprise surfaces remain outside the current static scan scope.

## Mosca-style risk model

The transparent 0–100 score combines quantum vulnerability, whether `data lifetime + migration time` overlaps the configured threat horizon, data sensitivity, business criticality, exposure, and migration effort. Every asset stores human-readable reasons behind its score. Recommendations depend on usage: key establishment, signature, TLS, hashing, or symmetric encryption.

## Outputs

| Endpoint | Purpose |
|---|---|
| `GET /api/dashboard/summary` | Latest assurance and risk posture |
| `GET /api/assets` | Filterable cryptographic inventory |
| `GET /api/cbom` | CycloneDX-style cryptographic bill of materials |
| `GET /api/reports/risk` | JSON risk and migration roadmap |
| `GET /api/reports/risk.txt` | Downloadable judge-friendly risk report |
| `GET /api/evidence-graph` | Asset/evidence nodes and support edges |
| `GET /api/evaluation` | Precision, recall, F1, per-source metrics, and declared blind spots |
| `GET /api/audit-logs` | Append-only audit history for Auditor/Admin roles |

Mutating requests accept `X-ECDAT-Role`; `admin` and `security_analyst` may scan or edit risk context. `auditor` and `viewer` are read-oriented roles. The prototype performs local deterministic analysis and stores certificate/key metadata—not private keys or source-code copies. Production deployments should enable PostgreSQL volume encryption, TLS, secrets management, and identity-provider authentication.

## Controlled evaluation dataset

`test-repo/ground_truth.json` defines expected assets. The dataset includes realistic Python and Java usage, RSA and ECDSA certificates, dependency-only TLS evidence, an intentional same-operation conflict, and runtime-generated crypto declared as a blind spot. The evaluation endpoint compares correlated output with this ground truth rather than inventing performance claims.

Add a test case by placing a supported `.py`, `.java`, `.js`, `.ts`, `.c`, `.cpp`, `.go`, `.cs`, `requirements.txt`, `pom.xml`, `.crt`, or `.pem` file below `test-repo/`, then update `ground_truth.json` with the expected component/algorithm pair.

## Verification

```bash
python -m compileall scanner backend scripts
python -m scanner.main test-repo
cd dashboard && npm run build
```
