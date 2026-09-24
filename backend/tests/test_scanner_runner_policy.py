"""Tests for deployment-configured scan risk defaults."""

from unittest.mock import patch

from backend.services.risk_engine import assess_risk
from backend.services.scanner_runner import _apply_risk_defaults


def test_threat_horizon_policy_can_promote_confirmed_quantum_risk() -> None:
    finding = {
        "algorithm": "RSA",
        "evidence_kind": "observed_operation",
    }

    with patch.dict("os.environ", {"ECDAT_DEFAULT_THREAT_HORIZON_YEARS": "10"}):
        configured = _apply_risk_defaults(finding)

    assert configured["threat_horizon_years"] == 10
    assert assess_risk(configured)["priority_label"] == "HIGH"
