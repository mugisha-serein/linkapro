# Domain Layer Unit Test - Risk Score Value Object
import pytest
from apps.accounts.domain.value_objects.risk_score import RiskScore, RiskLevel

def test_risk_score_level_consistency():
    risk = RiskScore(85, RiskLevel.CRITICAL, frozenset({'ip_reputation'}))
    assert risk.level == RiskLevel.CRITICAL
