from datetime import datetime
from typing import List
from django.db.models import Q

from payments.application.ports import IExpiryScanner
from payments.domain.entities import Payment as DomainPayment
from payments.application.ports import IKeyProvider
from django_app.payments.models import Payment as DjangoPayment
from .repositories import DjangoPaymentRepository


class DjangoExpiryScanner(IExpiryScanner):
    def __init__(self, key_provider: IKeyProvider):
        if key_provider is None:
            raise ValueError("key_provider is required")
        self.payment_repo = DjangoPaymentRepository(key_provider)

    def find_expired_pending(self, now: datetime) -> List[DomainPayment]:
        qs = DjangoPayment.objects.filter(
            status__in=["initiated", "pending"],
            expires_at__lt=now,
        ).select_related("user")
        return [self.payment_repo._to_domain(p) for p in qs]
