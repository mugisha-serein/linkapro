from __future__ import annotations

from datetime import date
import uuid

from django.db import IntegrityError
from django.db.models import F, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from django_app.vendors.models import VendorProfileViewed


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + months
    return date(month_index // 12, month_index % 12 + 1, 1)


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
    end_month = _shift_month(current_month, 1)

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
    counts = {
        row["month"].strftime("%Y-%m"): int(row["views"] or 0)
        for row in rows
    }
    return [
        {
            "month": _shift_month(start_month, offset).strftime("%Y-%m"),
            "views": counts.get(_shift_month(start_month, offset).strftime("%Y-%m"), 0),
        }
        for offset in range(months)
    ]
