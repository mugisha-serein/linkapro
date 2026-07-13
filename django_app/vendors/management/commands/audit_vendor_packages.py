import json

from django.core.management.base import BaseCommand

from django_app.vendors.models import ServicePackage as DjangoPackage
from domain.vendors.entities import ServicePackage
from domain.vendors.errors import PackageValidationError, VendorDomainError


class Command(BaseCommand):
    help = "Audit persisted vendor service packages against strict domain invariants."

    def handle(self, *args, **options):
        invalid_count = 0
        queryset = DjangoPackage.all_objects.order_by("id")

        for row in queryset.iterator(chunk_size=500):
            try:
                ServicePackage.rehydrate(
                    id=row.id,
                    vendor_id=row.vendor_id,
                    name=row.name,
                    description=row.description,
                    price=row.price,
                    currency=row.currency,
                    package_tier=row.package_tier,
                    approval_status=row.approval_status,
                    rejection_reason=row.rejection_reason,
                    is_active=row.is_active,
                    is_deleted=row.is_deleted,
                    deleted_at=row.deleted_at,
                    last_approved_at=row.last_approved_at,
                    last_vendor_public_edit_at=row.last_vendor_public_edit_at,
                    next_vendor_edit_allowed_at=row.next_vendor_edit_allowed_at,
                    version=row.version,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            except (PackageValidationError, VendorDomainError) as exc:
                invalid_count += 1
                self.stdout.write(
                    json.dumps(
                        {
                            "package_id": str(row.id),
                            "vendor_id": str(row.vendor_id),
                            "field_errors": exc.field_errors,
                        },
                        sort_keys=True,
                    )
                )

        if invalid_count:
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("No invalid vendor service packages found."))
