from datetime import date
from typing import Optional
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db.models import Count, Q

from domain.governance.entities import PlatformMetric as DomainMetric
from domain.governance.interfaces import IPlatformMetricRepository
from django_app.governance.models import PlatformMetric as DjangoMetric
from django_app.identity.models import User
from django_app.vendors.models import VendorProfile
from django_app.events.models import Event
from django_app.vendors.models import Inquiry
from fastapi_app.marketplace.models import ReviewModel  # adjust import as needed


class DjangoPlatformMetricRepository(IPlatformMetricRepository):
    def get_for_date(self, dt: date) -> Optional[DomainMetric]:
        try:
            obj = DjangoMetric.objects.get(date=dt)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def get_latest(self) -> Optional[DomainMetric]:
        obj = DjangoMetric.objects.order_by("-date").first()
        return self._to_domain(obj) if obj else None

    def save(self, domain_metric: DomainMetric) -> DomainMetric:
        obj, _ = DjangoMetric.objects.update_or_create(
            date=domain_metric.date,
            defaults={
                "total_users": domain_metric.total_users,
                "total_planners": domain_metric.total_planners,
                "total_vendors": domain_metric.total_vendors,
                "active_vendors": domain_metric.active_vendors,
                "pending_vendor_approvals": domain_metric.pending_vendor_approvals,
                "total_events": domain_metric.total_events,
                "total_inquiries": domain_metric.total_inquiries,
                "total_reviews": domain_metric.total_reviews,
                "updated_at": timezone.now(),
            }
        )
        return self._to_domain(obj)

    def generate_current_metrics(self) -> DomainMetric:
        today = timezone.now().date()
        total_users = User.objects.count()
        total_planners = User.objects.filter(role="planner").count()
        total_vendors = User.objects.filter(role="vendor").count()
        active_vendors = VendorProfile.objects.filter(status="approved").count()
        pending_approvals = VendorProfile.objects.filter(status="pending_review").count()
        total_events = Event.objects.count()
        total_inquiries = Inquiry.objects.count()
        total_reviews = ReviewModel.objects.count() if hasattr(ReviewModel, 'objects') else 0

        return DomainMetric(
            date=today,
            total_users=total_users,
            total_planners=total_planners,
            total_vendors=total_vendors,
            active_vendors=active_vendors,
            pending_vendor_approvals=pending_approvals,
            total_events=total_events,
            total_inquiries=total_inquiries,
            total_reviews=total_reviews,
            updated_at=timezone.now(),
        )

    def _to_domain(self, model: DjangoMetric) -> DomainMetric:
        return DomainMetric(
            date=model.date,
            total_users=model.total_users,
            total_planners=model.total_planners,
            total_vendors=model.total_vendors,
            active_vendors=model.active_vendors,
            pending_vendor_approvals=model.pending_vendor_approvals,
            total_events=model.total_events,
            total_inquiries=model.total_inquiries,
            total_reviews=model.total_reviews,
            updated_at=model.updated_at,
        )