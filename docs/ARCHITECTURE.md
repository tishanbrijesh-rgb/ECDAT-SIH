# ECDAT architecture

## System flow

```mermaid
flowchart LR
    U[Security analyst] --> UI[React assurance console]
    UI --> API[FastAPI control plane]
    API --> Q[Scan job]
    Q --> AST[Python AST collector]
    Q --> RULE[Multi-language rule collector]
    Q --> DEP[Dependency collector]
    Q --> CERT[X.509 collector]
    AST --> CORR[Logical evidence correlation]
    RULE --> CORR
    DEP --> CORR
    CERT --> CORR
    CORR --> CONF[Confidence and conflict analysis]
    CONF --> RISK[Mosca and PQC risk engine]
    RISK --> DB[(PostgreSQL or SQLite)]
    DB --> OUT[Inventory / CBOM / reports / graph / evaluation]
    OUT --> UI
```

## Assurance principles

- Confidence describes evidence strength; coverage describes measured scan scope. They are never treated as the same metric.
- Dependency evidence represents capability and is not promoted over stronger usage evidence in the same component.
- A conflict requires incompatible algorithms in the same operation and category, not merely multiple algorithms in one file.
- Every risk score stores its contributing context and human-readable reasons.
- The scanner remains local to the deployment; the prototype does not transmit source code.

## Deployment modes

- **Judge/local mode:** SQLite, two local processes, bundled controlled repository.
- **Compose mode:** PostgreSQL 16, backend and dashboard containers, read-only scanner input volume.
- **Future production mode:** authenticated repository ingestion, isolated workers, queue, secrets manager and organization SSO.
