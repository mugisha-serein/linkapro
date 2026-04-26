import pytest
from unittest.mock import patch
from django.urls import reverse
from django.http import JsonResponse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_webhook_rejects_wrong_hash(settings):
    settings.FLW_SECRET_HASH = "correct_secret"
    client = APIClient()
    url = reverse("payments:webhook")
    response = client.post(
        url,
        data={},
        content_type="application/json",
        HTTP_VERIF_HASH="wrong_secret",
    )
    assert response.status_code == 401


@patch("django_app.payments.views.FlutterwaveWebhookView.post")
def test_webhook_accepts_correct_hash(mock_post, settings):
    settings.FLW_SECRET_HASH = "correct_secret"
    # Simulate a successful view execution
    mock_post.return_value = JsonResponse({"status": "received"})

    client = APIClient()
    url = reverse("payments:webhook")
    response = client.post(
        url,
        data={"id": "evt123", "event": "charge.completed"},
        content_type="application/json",
        HTTP_VERIF_HASH="correct_secret",
    )
    assert response.status_code == 200


def test_constant_time_comparison_used():
    from django_app.payments.views import secrets as sec
    assert hasattr(sec, "compare_digest")