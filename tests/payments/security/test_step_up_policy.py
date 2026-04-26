import pytest
from django.http import JsonResponse
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory
from payments.domain.value_objects import Money, Currency
from payments.domain.step_up_policy import StepUpPolicy, StepUpPolicyResult
from domain.shared.utils import utc_now


class TestStepUpPolicy:
    # ---- Domain policy tests ----
    def test_below_threshold(self):
        money = Money(minor_units=200_000, currency=Currency("RWF"))   # 200k RWF < 500k
        result = StepUpPolicy.is_step_up_required(money, token_step_up=False, now=utc_now())
        assert result.required is False

    def test_above_threshold_without_step_up(self):
        money = Money(minor_units=600_000, currency=Currency("RWF"))   # 600k > 500k
        result = StepUpPolicy.is_step_up_required(money, token_step_up=False, now=utc_now())
        assert result.required is True
        assert "exceeds threshold" in result.reason

    def test_above_threshold_with_step_up(self):
        money = Money(minor_units=600_000, currency=Currency("RWF"))
        result = StepUpPolicy.is_step_up_required(money, token_step_up=True, now=utc_now())
        assert result.required is False

    def test_unsupported_currency_defaults_to_step_up(self):
        # Simulate missing threshold for a supported currency
        original = StepUpPolicy.THRESHOLDS.copy()
        del StepUpPolicy.THRESHOLDS["RWF"]
        try:
            money = Money(minor_units=100, currency=Currency("RWF"))  # RWF is still a valid Currency
            result = StepUpPolicy.is_step_up_required(money, token_step_up=False, now=utc_now())
            assert result.required is True
            assert "Unsupported currency" in result.reason
        finally:
            StepUpPolicy.THRESHOLDS = original