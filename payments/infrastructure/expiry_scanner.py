from datetime import datetime
from typing import List
from django.db.models import Q

from payments.application.ports import IExpiryScanner
from payments.domain.entities import Payment as DomainPayment
from django_app.payments.models import Payment as DjangoPayment
from .repositories import DjangoPaymentRepository


class DjangoExpiryScanner(IExpiryScanner):
    def find_expired_pending(self, now: datetime) -> List[DomainPayment]:
        qs = DjangoPayment.objects.filter(
            status__in=["initiated", "pending"],
            expires_at__lt=now,
        ).select_related("user")
        repo = DjangoPaymentRepository()
        return [repo._to_domain(p) for p in qs]