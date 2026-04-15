# Domain Layer Unit Test - Security Policy
import pytest
from apps.accounts.domain.services.security_policy import SecurityPolicy

class DummyAttempt:
    pass

def test_evaluate_risk_ip_reputation():
    attempt = DummyAttempt()
    context = {'ip_reputation': 'bad'}
    assert SecurityPolicy.evaluate_risk(attempt, context) >= 40

def test_detect_anomaly_geo():
    attempt = DummyAttempt()
    context = {'geo_anomaly': True}
    assert SecurityPolicy.detect_anomaly(attempt, context) is True
