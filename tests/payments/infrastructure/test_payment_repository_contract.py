import uuid
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from django_app.identity.models import User
from django_app.payments.models import ApiKey, Payment as DjangoPayment
from payments.domain.entities import Payment as DomainPayment
from payments.domain.enums import PaymentEnv, PaymentMethod, PaymentStatus
from payments.domain.value_objects import Currency, Money
from payments.infrastructure.key_manager import create_api_key
from payments.infrastructure.repositories import DjangoPaymentRepository, DjangoApiKeyRepository
from domain.shared.utils import utc_now


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def key_provider():
    provider = MagicMock()
    provider._last_dek = None

    def wrap_dek(dek):
        provider._last_dek = dek
        return b"wrapped-dek"

    def unwrap_dek(_wrapped):
        return provider._last_dek

    provider.wrap_dek.side_effect = wrap_dek
    provider.unwrap_dek.side_effect = unwrap_dek
    return provider


def test_payment_repository_round_trips_crypto_contract(key_provider):
    repo = DjangoPaymentRepository(key_provider)
    user = User.objects.create_user(
        email="payer@example.com",
        password="password123",
        first_name="Pay",
        last_name="Er",
        role="planner",
    )
    payment = DomainPayment(
        id=uuid.uuid4(),
        user_id=user.id,
        amount=Money(1000, Currency("RWF")),
        method=PaymentMethod.CARD,
        reference="pay_ref_123",
        idempotency_key=str(uuid.uuid4()),
        environment=PaymentEnv.TEST,
        status=PaymentStatus.PENDING,
        provider_reference="flw_ref_123",
        context_reference="ctx_ref_123",
        metadata={"order_id": "ord_1", "source": "web"},
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(days=1),
    )

    saved = repo.save(payment)

    assert payment.metadata == {"order_id": "ord_1", "source": "web"}
    assert payment.provider_reference == "flw_ref_123"
    assert payment.context_reference == "ctx_ref_123"
    assert key_provider.wrap_dek.called

    model = DjangoPayment.objects.get(reference="pay_ref_123")
    assert model.dek_encrypted == b"wrapped-dek"
    assert model.provider_reference == "flw_ref_123"
    assert model.context_reference == "ctx_ref_123"
    assert isinstance(model.metadata, dict)
    assert model.metadata["dek_encrypted"] == "d3JhcHBlZC1kZWs="
    assert model.provider_reference_hash is not None

    loaded = repo.find_by_reference("pay_ref_123")
    assert loaded is not None
    assert loaded.metadata == {"order_id": "ord_1", "source": "web"}
    assert loaded.provider_reference == "flw_ref_123"
    assert loaded.context_reference == "ctx_ref_123"
    assert saved.reference == "pay_ref_123"


def test_velocity_context_uses_valid_orm_aggregation(key_provider):
    repo = DjangoPaymentRepository(key_provider)
    user = User.objects.create_user(
        email="velocity@example.com",
        password="password123",
        first_name="Vel",
        last_name="Oc",
        role="planner",
    )

    base_kwargs = dict(
        user_id=user.id,
        amount=Money(1000, Currency("RWF")),
        method=PaymentMethod.CARD,
        environment=PaymentEnv.TEST,
        status=PaymentStatus.PENDING,
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(days=1),
    )

    repo.save(
        DomainPayment(
            id=uuid.uuid4(),
            reference="pay_v1",
            idempotency_key="idem_v1",
            provider_reference="prov_v1",
            context_reference="ctx_v1",
            metadata={},
            **base_kwargs,
        )
    )
    repo.save(
        DomainPayment(
            id=uuid.uuid4(),
            reference="pay_v2",
            idempotency_key="idem_v2",
            provider_reference="prov_v2",
            context_reference="ctx_v2",
            metadata={},
            **base_kwargs,
        )
    )

    ctx = repo.get_velocity_context(user.id, utc_now())
    assert ctx.payments_last_day >= 2
    assert ctx.amount_last_day_minor >= 2000


def test_api_key_generation_populates_plain_secret_contract():
    user = User.objects.create_user(
        email="api@example.com",
        password="password123",
        first_name="Api",
        last_name="Key",
        role="planner",
    )

    key_id, secret = create_api_key(user, scopes=["initiate_payment"])

    record = ApiKey.objects.get(key_id=key_id)
    assert record.secret_plain == secret
    assert record.key_hash

    repo = DjangoApiKeyRepository()
    key_data = repo.find_by_key_id(key_id)
    assert key_data is not None
    assert key_data["secret"] == secret
