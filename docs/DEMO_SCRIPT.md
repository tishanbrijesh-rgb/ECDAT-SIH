# Five-minute SIH demonstration

## 0:00–0:40 — Problem

Organizations cannot migrate to post-quantum cryptography until they know where cryptography exists, how reliable each observation is and which assets must move first.

## 0:40–1:20 — Start a measured scan

1. Open **New scan**.
2. Keep `/test-repo` selected.
3. Start discovery.
4. Point out the four independent collectors and measured supported-file coverage.

## 1:20–2:10 — Explain discovery assurance

1. Open **Inventory**.
2. Show AST, rule, dependency and certificate evidence.
3. Explain that confidence is evidence strength while coverage is scan visibility.
4. Open the intentional `AmbiguousCipher.java` conflict and show the confidence penalty.

## 2:10–3:15 — Demonstrate quantum prioritization

1. Open an RSA or ECDSA asset.
2. Change sensitivity, business criticality, exposure, data lifetime and migration effort.
3. Show immediate risk recalculation, Mosca planning window and ML-KEM/ML-DSA guidance.
4. Explain when a hybrid transition is recommended.

## 3:15–4:10 — Show outputs

1. Return to the overview.
2. Show precision, recall and F1 for the controlled ground truth.
3. Download the risk report.
4. Open the CycloneDX-style CBOM.
5. Mention the evidence graph and append-only audit endpoint.

## 4:10–5:00 — Close honestly

- ECDAT is privacy-first and explainable.
- It reports explicit blind spots rather than claiming universal visibility.
- The architecture supports future repository connectors, isolated workers and runtime/cloud collectors.
- The included result is a controlled evaluation, not an unsupported enterprise accuracy claim.

## Recovery

- Dashboard: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`
- Readiness: `http://localhost:8000/ready`
- If Docker is unavailable, use the two local commands in the README.
