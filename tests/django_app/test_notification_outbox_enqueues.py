import uuid
from unittest.mock import patch

import pytest
from django.utils import timezone

from django_app.documents.models import DocumentDomainEventOutbox, ExportJob
from django_app.events.models import Event
from django_app.identity.models import User
from django_app.payments.models import Payment, PaymentDomainEventOutbox
from django_app.vendors.models import Inquiry, VendorDomainEventOutbox, VendorProfile
from tasks.document_domain_events import publish_document_domain_event
from tasks.payment_domain_events import publish_payment_domain_event
from tasks.vendor_domain_events import publish_vendor_domain_event


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("domain", "event_type", "expected_template"),
    [
        ("vendor", "VendorSubmittedForReview", "vendor_submitted_for_review"),
        ("vendor", "VendorApproved", "vendor_approved"),
        ("vendor", "VendorRejected", "vendor_rejected"),
        ("vendor", "VendorSuspended", "vendor_suspended"),
        ("vendor", "VendorReinstated", "vendor_reinstated"),
        ("vendor", "VendorProfileUpdated", "vendor_profile_updated"),
        ("vendor", "InquiryReceived", "inquiry_received"),
        ("payment", "PaymentCompleted", "payment_completed"),
        ("payment", "PaymentExpired", "payment_expired"),
        ("document", "ExportCompleted", "export_completed"),
    ],
)
def test_send_email_task_is_enqueued_for_each_mapped_event_type(
    domain,
    event_type,
    expected_template,
    settings,
):
    settings.FRONTEND_URL = "https://linkapro.test"

    with patch("tasks.notifications.send_email_task.delay") as delay:
        if domain == "vendor":
            event = _vendor_event(event_type)
            assert publish_vendor_domain_event(event.id) is True
            expected_to = "vendor@example.com"
        elif domain == "payment":
            event = _payment_event(event_type)
            assert publish_payment_domain_event(event.id) is True
            expected_to = "payer@example.com"
        else:
            event = _document_event(event_type)
            assert publish_document_domain_event(event.id) is True
            expected_to = "planner@example.com"

        delay.assert_called_once()
        payload = delay.call_args.kwargs

    assert payload["to"] == expected_to
    assert payload["template"] == expected_template
    assert payload["context"]["cta_url"]
    _assert_context_shape(event_type, payload["context"])


def _vendor_event(event_type: str) -> VendorDomainEventOutbox:
    user = User.objects.create_user(
        email=f"{uuid.uuid4().hex}@vendor-user.example",
        password="pass",
        first_name="Vendor",
        last_name="User",
        role="vendor",
    )
    vendor = VendorProfile.objects.create(
        user=user,
        business_name="Kigali Events",
        category=VendorProfile.Category.PHOTOGRAPHY,
        description="A complete vendor description.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
        status=VendorProfile.Status.PENDING_REVIEW,
    )
    payload = {"vendor_id": str(vendor.id)}
    if event_type in {"VendorRejected", "VendorSuspended"}:
        payload["reason"] = "Needs an update."
    if event_type == "InquiryReceived":
        inquiry = Inquiry.objects.create(
            vendor=vendor,
            client_name="Aline",
            client_email="aline@example.com",
            message="Please share availability.",
        )
        payload["inquiry_id"] = str(inquiry.id)
    return VendorDomainEventOutbox.objects.create(
        event_id=uuid.uuid4(),
        aggregate_id=vendor.id,
        aggregate_version=1,
        event_type=event_type,
        occurred_at=timezone.now(),
        payload=payload,
    )


def _payment_event(event_type: str) -> PaymentDomainEventOutbox:
    user = User.objects.create_user(
        email="payer@example.com",
        password="pass",
        first_name="Paying",
        last_name="Planner",
        role="planner",
    )
    payment = Payment.objects.create(
        user=user,
        amount_minor=15000,
        currency="RWF",
        method=Payment.Method.CARD,
        status=Payment.Status.SUCCESS if event_type == "PaymentCompleted" else Payment.Status.EXPIRED,
        reference=f"pay_{uuid.uuid4().hex[:8]}",
        idempotency_key=str(uuid.uuid4()),
        environment=Payment.Environment.TEST,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )
    return PaymentDomainEventOutbox.objects.create(
        event_id=uuid.uuid4(),
        aggregate_id=payment.id,
        aggregate_version=0,
        event_type=event_type,
        occurred_at=timezone.now(),
        payload={"payment_id": str(payment.id)},
    )


def _document_event(event_type: str) -> DocumentDomainEventOutbox:
    user = User.objects.create_user(
        email="planner@example.com",
        password="pass",
        first_name="Planning",
        last_name="User",
        role="planner",
    )
    event = Event.objects.create(
        planner=user,
        name="Wedding",
        event_type="wedding",
        event_date=timezone.now().date(),
    )
    job = ExportJob.objects.create(
        event=event,
        requested_by=user,
        export_type=ExportJob.ExportType.TIMELINE,
        status=ExportJob.Status.COMPLETED,
        file_url="https://cdn.example.com/timeline.pdf",
    )
    return DocumentDomainEventOutbox.objects.create(
        event_id=uuid.uuid4(),
        aggregate_id=job.id,
        aggregate_version=0,
        event_type=event_type,
        occurred_at=timezone.now(),
        payload={"job_id": str(job.id)},
    )


def _assert_context_shape(event_type: str, context: dict) -> None:
    if event_type == "InquiryReceived":
        assert set(context) == {"business_name", "client_name", "cta_url"}
        assert context["client_name"] == "Aline"
    elif event_type.startswith("Vendor"):
        assert {"business_name", "cta_url"} <= set(context)
        if event_type in {"VendorRejected", "VendorSuspended"}:
            assert context["reason"] == "Needs an update."
    elif event_type.startswith("Payment"):
        assert set(context) == {"payment_reference", "amount", "currency", "status", "cta_url"}
        assert context["amount"] == "15000"
        assert context["currency"] == "RWF"
    else:
        assert set(context) == {"event_name", "export_type", "file_url", "cta_url"}
        assert context["event_name"] == "Wedding"
