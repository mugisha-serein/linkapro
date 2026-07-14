from __future__ import annotations

from datetime import date, datetime, time
import uuid

from django.db import IntegrityError
from django.db.models import Avg, Count, F, Min, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from domain.vendors.profile.entity import VendorProfile as DomainVendorProfile
from domain.vendors.profile.rules import get_profile_completion_errors
from django_app.governance.models import AuditLog
from django_app.vendors.models import (
    Inquiry,
    PortfolioImage,
    ServicePackage,
    VendorProfile as DjangoVendorProfile,
    VendorProfileViewed,
)

MARKETPLACE_SEARCH_IMPRESSIONS = "marketplace_search_impressions"
INQUIRY_CONVERSION_RATE = "inquiry_conversion_rate"
PORTFOLIO_QUALITY_SNAPSHOTS = "portfolio_quality_snapshots"
PORTFOLIO_QUALITY_SNAPSHOT_PROPOSAL = {
    "model": "PortfolioQualitySnapshot",
    "fields": {
        "vendor_id": "ForeignKey(VendorProfile)",
        "snapshot_date": "date",
        "average_analyzer_score": "decimal",
        "active_image_count": "integer",
    },
    "unique": ("vendor_id", "snapshot_date"),
}
PORTFOLIO_IMAGE_VIEWS = "portfolio_image_views"
PORTFOLIO_IMAGE_ENGAGEMENTS = "portfolio_image_engagements"
PORTFOLIO_IMAGE_ENGAGEMENT_PROPOSAL = {
    "model": "PortfolioImageEngagementDaily",
    "fields": {
        "vendor_id": "ForeignKey(VendorProfile)",
        "image_id": "ForeignKey(PortfolioImage)",
        "event_date": "date",
        "view_count": "integer",
        "engagement_count": "integer",
    },
    "unique": ("image_id", "event_date"),
}
INQUIRY_CONVERSION_STATUS_PROPOSAL = {
    "model": "Inquiry",
    "field": "status",
    "type": "enum",
    "values": ("new", "responded", "converted", "declined"),
}


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _monthly_counts(
    queryset,
    *,
    date_field: str,
    count_alias: str,
    start_month: date,
    months: int,
    datetime_bounds: bool = False,
) -> list[dict[str, int | str]]:
    end_month = _shift_month(start_month, months)
    start_boundary = start_month
    end_boundary = end_month
    if datetime_bounds:
        start_boundary = timezone.make_aware(datetime.combine(start_month, time.min))
        end_boundary = timezone.make_aware(datetime.combine(end_month, time.min))
    filters = {
        f"{date_field}__gte": start_boundary,
        f"{date_field}__lt": end_boundary,
    }
    rows = (
        queryset.filter(**filters)
        .annotate(month=TruncMonth(date_field))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    counts = {row["month"].strftime("%Y-%m"): int(row["count"] or 0) for row in rows}
    return [
        {
            "month": month.strftime("%Y-%m"),
            count_alias: counts.get(month.strftime("%Y-%m"), 0),
        }
        for month in (_shift_month(start_month, offset) for offset in range(months))
    ]


def _monthly_view_counts(vendor_id: uuid.UUID, *, start_month: date, months: int) -> list[dict[str, int | str]]:
    end_month = _shift_month(start_month, months)
    rows = (
        VendorProfileViewed.objects.filter(
            vendor_id=vendor_id,
            view_date__gte=start_month,
            view_date__lt=end_month,
        )
        .annotate(month=TruncMonth("view_date"))
        .values("month")
        .annotate(views=Sum("view_count"))
        .order_by("month")
    )
    counts = {row["month"].strftime("%Y-%m"): int(row["views"] or 0) for row in rows}
    return [
        {
            "month": month.strftime("%Y-%m"),
            "views": counts.get(month.strftime("%Y-%m"), 0),
        }
        for month in (_shift_month(start_month, offset) for offset in range(months))
    ]


def log_profile_view(vendor_id: uuid.UUID, *, viewed_on: date | None = None) -> None:
    view_date = viewed_on or timezone.localdate()
    updated = VendorProfileViewed.objects.filter(
        vendor_id=vendor_id,
        view_date=view_date,
    ).update(view_count=F("view_count") + 1)
    if updated:
        return
    try:
        VendorProfileViewed.objects.create(
            vendor_id=vendor_id,
            view_date=view_date,
            view_count=1,
        )
    except IntegrityError:
        VendorProfileViewed.objects.filter(
            vendor_id=vendor_id,
            view_date=view_date,
        ).update(view_count=F("view_count") + 1)


def total_views_trend(vendor_id: uuid.UUID, months: int = 6) -> list[dict[str, int | str]]:
    if months < 1:
        raise ValueError("months must be positive")

    current_month = _month_start(timezone.localdate())
    start_month = _shift_month(current_month, -(months - 1))
    return _monthly_view_counts(vendor_id, start_month=start_month, months=months)


def views_by_month(vendor_id: uuid.UUID, year: int) -> list[dict[str, int | str]]:
    if isinstance(year, bool):
        raise ValueError("year must be an integer")
    year = int(year)
    if year < 1:
        raise ValueError("year must be positive")
    return _monthly_view_counts(vendor_id, start_month=date(year, 1, 1), months=12)


def inquiries_by_month(vendor_id: uuid.UUID, months: int = 6) -> list[dict[str, int | str]]:
    if months < 1:
        raise ValueError("months must be positive")

    current_month = _month_start(timezone.localdate())
    start_month = _shift_month(current_month, -(months - 1))
    return _monthly_counts(
        Inquiry.objects.filter(vendor_id=vendor_id),
        date_field="created_at",
        count_alias="inquiries",
        start_month=start_month,
        months=months,
        datetime_bounds=True,
    )


def visibility_trend(vendor_id: uuid.UUID, months: int = 6) -> dict[str, object]:
    profile_views = total_views_trend(vendor_id, months=months)
    return {
        "points": [
            {
                "month": point["month"],
                "profile_views": point["views"],
                "marketplace_impressions": None,
            }
            for point in profile_views
        ],
        "unavailable_metrics": (MARKETPLACE_SEARCH_IMPRESSIONS,),
    }


def portfolio_quality_trend(vendor_id: uuid.UUID) -> dict[str, object]:
    current = PortfolioImage.objects.filter(
        vendor_id=vendor_id,
        is_active=True,
        analyzer_score__isnull=False,
    ).aggregate(
        average_score=Avg("analyzer_score"),
        scored_images=Count("id"),
    )
    average_score = current["average_score"]
    return {
        "current_average_score": None if average_score is None else round(float(average_score), 2),
        "scored_images": current["scored_images"] or 0,
        "points": [],
        "unavailable_metrics": (PORTFOLIO_QUALITY_SNAPSHOTS,),
        "schema_gap": (
            "PortfolioImage stores only the current analyzer_score. A real quality trend "
            "requires periodic snapshots of the average analyzer_score over time."
        ),
        "proposed_schema": PORTFOLIO_QUALITY_SNAPSHOT_PROPOSAL,
    }


def portfolio_analytics(vendor_id: uuid.UUID) -> dict[str, object]:
    quality_trend = portfolio_quality_trend(vendor_id)
    portfolio_count = PortfolioImage.objects.filter(vendor_id=vendor_id, is_active=True).count()
    return {
        "portfolio_count": portfolio_count,
        "quality_trend": quality_trend,
        "per_image_metrics": None,
        "unavailable_metrics": (
            *quality_trend["unavailable_metrics"],
            PORTFOLIO_IMAGE_VIEWS,
            PORTFOLIO_IMAGE_ENGAGEMENTS,
        ),
        "schema_gap": (
            "PortfolioImage has no per-image view or engagement tracking today. "
            "Only profile-level views are recorded, so per-image portfolio analytics "
            "cannot be derived without a dedicated tracking table."
        ),
        "proposed_schema": PORTFOLIO_IMAGE_ENGAGEMENT_PROPOSAL,
    }


def profile_strength_score(vendor_id: uuid.UUID) -> int:
    profile = DjangoVendorProfile.objects.get(id=vendor_id)
    required_fields = DomainVendorProfile.required_profile_fields()
    if not required_fields:
        return 100
    errors = get_profile_completion_errors(profile)
    complete_fields = sum(1 for field_name in required_fields if field_name not in errors)
    score = round((complete_fields / len(required_fields)) * 100)
    if errors:
        return min(score, 99)
    return score


def active_packages_count(vendor_id: uuid.UUID) -> int:
    return ServicePackage.all_objects.filter(
        vendor_id=vendor_id,
        is_deleted=False,
        is_active=True,
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
    ).count()


def inquiry_response_metrics(vendor_id: uuid.UUID, *, now=None) -> dict[str, object]:
    now = now or timezone.now()
    counts = Inquiry.objects.filter(vendor_id=vendor_id).aggregate(
        total_inquiries=Count("id"),
        unread_inquiries=Count("id", filter=Q(is_read=False)),
        read_inquiries=Count("id", filter=Q(is_read=True)),
        inquiries_mtd=Count(
            "id",
            filter=Q(created_at__year=now.year, created_at__month=now.month),
        ),
        oldest_unread_at=Min("created_at", filter=Q(is_read=False)),
    )
    return {
        "total_inquiries": counts["total_inquiries"] or 0,
        "unread_inquiries": counts["unread_inquiries"] or 0,
        "read_inquiries": counts["read_inquiries"] or 0,
        "inquiries_mtd": counts["inquiries_mtd"] or 0,
        "oldest_unread_at": counts["oldest_unread_at"],
    }


def response_rate(vendor_id: uuid.UUID) -> float:
    counts = inquiry_response_metrics(vendor_id)
    total = counts["total_inquiries"] or 0
    read = counts["read_inquiries"] or 0
    return round((read / total) * 100, 2) if total else 0.0


def response_backlog(vendor_id: uuid.UUID) -> dict[str, object]:
    counts = inquiry_response_metrics(vendor_id)
    oldest_unread_at = counts["oldest_unread_at"]
    oldest_unread_age_hours = None
    if oldest_unread_at is not None:
        oldest_unread_age_hours = round((timezone.now() - oldest_unread_at).total_seconds() / 3600, 2)
    return {
        "count": counts["unread_inquiries"],
        "oldest_unread_at": oldest_unread_at.isoformat() if oldest_unread_at else None,
        "oldest_unread_age_hours": oldest_unread_age_hours,
    }


def inquiry_conversion_rate(vendor_id: uuid.UUID) -> dict[str, object]:
    return {
        "vendor_id": str(vendor_id),
        "conversion_rate": None,
        "unavailable_metrics": (INQUIRY_CONVERSION_RATE,),
        "schema_gap": (
            "Inquiry has no converted/booked/hired signal today; is_read only "
            "means the vendor opened the inquiry and cannot support conversion."
        ),
        "proposed_schema": INQUIRY_CONVERSION_STATUS_PROPOSAL,
    }


def recent_security_actions(vendor_id: uuid.UUID, limit: int = 10) -> list[dict[str, object]]:
    if isinstance(limit, bool):
        raise ValueError("limit must be a positive integer")
    limit = int(limit)
    if limit < 1:
        raise ValueError("limit must be a positive integer")
    logs = (
        AuditLog.objects.select_related("admin")
        .filter(target_id=vendor_id)
        .order_by("-created_at", "-id")[:limit]
    )
    return [
        {
            "id": str(log.id),
            "admin": str(log.admin_id) if log.admin_id else None,
            "action_type": log.action_type,
            "target_type": log.target_type,
            "target_id": str(log.target_id),
            "details": log.details,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
