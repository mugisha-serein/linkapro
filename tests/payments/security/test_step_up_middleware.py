import json
import pytest
from unittest.mock import MagicMock, patch
from django.http import JsonResponse
from django.test import RequestFactory
from payments.infrastructure.step_up_middleware import StepUpEnforcementMiddleware


class TestStepUpMiddleware:
    @pytest.fixture
    def factory(self):
        return RequestFactory()

    @pytest.fixture
    def middleware(self):
        # Return middleware instance with a dummy get_response
        def get_response(request):
            return JsonResponse({"status": "ok"})
        return StepUpEnforcementMiddleware(get_response)

    def test_payment_below_threshold_passes(self, middleware, factory):
        request = factory.post("/api/django/payments/initiate/",
                               data=json.dumps({"amount": "1000.00", "currency": "RWF"}),
                               content_type="application/json")
        # Simulate authenticated user with token payload (step_up=False)
        request.auth = MagicMock()
        request.auth.payload = {"step_up": False, "user_id": "abc"}

        response = middleware(request)
        assert response.status_code == 200   # passed through

    def test_payment_above_threshold_without_step_up_returns_403(self, middleware, factory):
        request = factory.post("/api/django/payments/initiate/",
                               data=json.dumps({"amount": "600000.00", "currency": "RWF"}),
                               content_type="application/json")
        request.auth = MagicMock()
        request.auth.payload = {"step_up": False}

        response = middleware(request)
        assert response.status_code == 403
        data = json.loads(response.content)
        assert data["error"] == "step_up_required"

    def test_payment_above_threshold_with_step_up_passes(self, middleware, factory):
        request = factory.post("/api/django/payments/initiate/",
                               data=json.dumps({"amount": "600000.00", "currency": "RWF"}),
                               content_type="application/json")
        request.auth = MagicMock()
        request.auth.payload = {"step_up": True}

        response = middleware(request)
        assert response.status_code == 200

    def test_non_payment_path_ignored(self, middleware, factory):
        request = factory.get("/api/django/payments/status/ref/")
        # No auth needed
        response = middleware(request)
        assert response.status_code == 200

    def test_missing_amount_gracefully_skips(self, middleware, factory):
        request = factory.post("/api/django/payments/initiate/",
                               data=json.dumps({"currency": "RWF"}),
                               content_type="application/json")
        request.auth = MagicMock()
        request.auth.payload = {"step_up": False}
        response = middleware(request)
        assert response.status_code == 200   # let view handle validation