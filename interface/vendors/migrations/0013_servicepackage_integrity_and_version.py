from django.db import migrations, models
from django.db.models import F, Q


VALID_APPROVAL_STATUSES = {"waiting_approval", "approved", "rejected"}
VALID_PACKAGE_TIERS = {"standard", "premier", "gold"}


def repair_service_package_state(apps, schema_editor):
    ServicePackage = apps.get_model("vendors", "ServicePackage")
    manual = []

    manager = ServicePackage._base_manager
    queryset = manager.all().only(
        "id",
        "vendor_id",
        "currency",
        "approval_status",
        "package_tier",
        "rejection_reason",
    )
    for package in queryset.iterator(chunk_size=500):
        fields = []
        if package.currency != "RWF":
            fields.append("currency")
        if package.approval_status not in VALID_APPROVAL_STATUSES:
            fields.append("approval_status")
        if package.package_tier not in VALID_PACKAGE_TIERS:
            fields.append("package_tier")
        if package.approval_status == "rejected" and not package.rejection_reason:
            fields.append("rejection_reason")
        if fields:
            manual.append((str(package.id), str(package.vendor_id), fields))

    if manual:
        print("ServicePackage rows require manual correction before integrity constraints can be added:")
        for package_id, vendor_id, fields in manual:
            print(f"package_id={package_id} vendor_id={vendor_id} fields={','.join(fields)}")
        raise RuntimeError("Unrepairable ServicePackage rows found.")

    manager.filter(
        approval_status__in=["waiting_approval", "rejected"],
        is_active=True,
    ).update(is_active=False)
    manager.filter(is_deleted=True, is_active=True).update(is_active=False)
    manager.filter(is_deleted=True, deleted_at__isnull=True).update(deleted_at=F("updated_at"))
    manager.filter(
        approval_status="approved",
        last_approved_at__isnull=True,
    ).update(last_approved_at=F("updated_at"))
    manager.exclude(approval_status="rejected").filter(
        Q(rejection_reason__isnull=False) & ~Q(rejection_reason="")
    ).update(rejection_reason=None)


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0012_vendorprofile_cover_image_public_id_and_more"),
    ]

    operations = [
        migrations.RunPython(repair_service_package_state, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="servicepackage",
            name="currency",
            field=models.CharField(choices=[("RWF", "RWF")], default="RWF", max_length=3),
        ),
        migrations.AlterField(
            model_name="servicepackage",
            name="is_active",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="servicepackage",
            name="version",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="servicepackage",
            constraint=models.CheckConstraint(condition=Q(currency="RWF"), name="vendors_servicepackage_currency_rwf"),
        ),
        migrations.AddConstraint(
            model_name="servicepackage",
            constraint=models.CheckConstraint(
                condition=Q(is_deleted=False) | Q(is_active=False),
                name="vendors_servicepackage_deleted_inactive",
            ),
        ),
        migrations.AddConstraint(
            model_name="servicepackage",
            constraint=models.CheckConstraint(
                condition=Q(is_deleted=False) | Q(deleted_at__isnull=False),
                name="vendors_servicepackage_deleted_at_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="servicepackage",
            constraint=models.CheckConstraint(
                condition=~Q(approval_status="waiting_approval") | Q(is_active=False),
                name="vendors_servicepackage_waiting_inactive",
            ),
        ),
        migrations.AddConstraint(
            model_name="servicepackage",
            constraint=models.CheckConstraint(
                condition=~Q(approval_status="approved") | Q(last_approved_at__isnull=False),
                name="vendors_servicepackage_approved_at_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="servicepackage",
            constraint=models.CheckConstraint(
                condition=~Q(approval_status="rejected") | Q(is_active=False),
                name="vendors_servicepackage_rejected_inactive",
            ),
        ),
        migrations.AddConstraint(
            model_name="servicepackage",
            constraint=models.CheckConstraint(
                condition=(
                    ~Q(approval_status="rejected")
                    | (Q(rejection_reason__isnull=False) & ~Q(rejection_reason=""))
                ),
                name="vendors_servicepackage_rejected_reason_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="servicepackage",
            constraint=models.CheckConstraint(
                condition=(
                    Q(approval_status="rejected")
                    | Q(rejection_reason__isnull=True)
                    | Q(rejection_reason="")
                ),
                name="vendors_servicepackage_rejection_only_rejected",
            ),
        ),
    ]
