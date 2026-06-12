import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.payments.models import Payment as DjangoPayment
from payments.application.query_handlers import PaymentQueryHandlers
from payments.domain.entities import Payment as DomainPayment
from payments.domain.enums import PaymentEnv, PaymentMethod, PaymentStatus
from payments.domain.value_objects import Currency, Money


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def payment_middleware_settings(settings):
    settings.REDIS_URL = "redis://localhost:6379/0"


class FakePaymentRepository:
    def __init__(self, payment):
        self.payment = payment

    def find_by_reference(self, reference):
        if reference == self.payment.reference:
            return self.payment
        return None


@pytest.fixture
def users():
    user_a = User.objects.create_user(
        email="payer-a@example.com",
        password="password123",
        first_name="Payer",
        last_name="A",
        role="planner",
    )
    user_b = User.objects.create_user(
        email="payer-b@example.com",
        password="password123",
        first_name="Payer",
        last_name="B",
        role="planner",
    )
    return user_a, user_b


def create_payment(user, reference, status, amount_minor):
    return DjangoPayment.objects.create(
        user=user,
        amount_minor=amount_minor,
        currency="RWF",
        method=DjangoPayment.Method.CARD,
        status=status,
        reference=reference,
        idempotency_key=str(uuid.uuid4()),
        environment=DjangoPayment.Environment.TEST,
        expires_at=timezone.now() + timedelta(days=1),
    )


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_AUTHORIZATION="Bearer test-token")
    return client


def test_payment_status_is_scoped_to_authenticated_user(users, monkeypatch):
    user_a, user_b = users
    payment = DomainPayment(
        id=uuid.uuid4(),
        user_id=user_b.id,
        amount=Money(5000, Currency("RWF")),
        method=PaymentMethod.CARD,
        reference="owned-by-b",
        idempotency_key=str(uuid.uuid4()),
        environment=PaymentEnv.TEST,
        status=PaymentStatus.PENDING,
        provider_reference="provider-ref",
        context_reference=None,
        metadata={},
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
    )
    handlers = PaymentQueryHandlers(FakePaymentRepository(payment))
    monkeypatch.setattr("django_app.payments.views.get_query_handlers", lambda: handlers)

    client = authenticated_client(user_a)
    response = client.get(reverse("payments:status", args=["owned-by-b"]))

    assert response.status_code == 404
    assert response.data == {"error": "Payment not found"}

    client = authenticated_client(user_b)
    response = client.get(reverse("payments:status", args=["owned-by-b"]))

    assert response.status_code == 200
    assert response.data["reference"] == "owned-by-b"


def test_payment_list_returns_only_authenticated_users_payments(users):
    user_a, user_b = users
    create_payment(user_a, "pay-a", DjangoPayment.Status.PENDING, 1000)
    create_payment(user_b, "pay-b", DjangoPayment.Status.SUCCESS, 2000)

    client = authenticated_client(user_a)
    response = client.get(reverse("payments:list"))

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert [item["reference"] for item in response.data["results"]] == ["pay-a"]


def test_payment_summary_counts_only_authenticated_users_payments(users):
    user_a, user_b = users
    create_payment(user_a, "pay-a-success", DjangoPayment.Status.SUCCESS, 1000)
    create_payment(user_a, "pay-a-pending", DjangoPayment.Status.PENDING, 2500)
    create_payment(user_b, "pay-b-success", DjangoPayment.Status.SUCCESS, 9000)

    client = authenticated_client(user_a)
    response = client.get(reverse("payments:summary"))

    assert response.status_code == 200
    assert response.data["total_payments"] == 2
    assert response.data["successful_payments"] == 1
    assert response.data["pending_payments"] == 1
    assert response.data["failed_payments"] == 0
    assert response.data["total_paid"] == "1000"
    assert response.data["pending_amount"] == "2500"
