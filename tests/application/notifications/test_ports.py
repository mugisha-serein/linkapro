from application.notifications.event_map import (
    DOCUMENT_EVENT_TO_TEMPLATE,
    IDENTITY_EVENT_TO_TEMPLATE,
    PAYMENT_EVENT_TO_TEMPLATE,
    VENDOR_EVENT_TO_TEMPLATE,
    export_notification_context,
    identity_notification_context,
    payment_notification_context,
    vendor_notification_context,
)


def test_notification_event_template_maps_are_explicit():
    assert VENDOR_EVENT_TO_TEMPLATE == {
        "VendorSubmittedForReview": "vendor_submitted_for_review",
        "VendorApproved": "vendor_approved",
        "VendorRejected": "vendor_rejected",
        "VendorSuspended": "vendor_suspended",
        "VendorReinstated": "vendor_reinstated",
        "VendorProfileUpdated": "vendor_profile_updated",
        "InquiryReceived": "inquiry_received",
    }
    assert PAYMENT_EVENT_TO_TEMPLATE == {
        "PaymentCompleted": "payment_completed",
        "PaymentExpired": "payment_expired",
    }
    assert DOCUMENT_EVENT_TO_TEMPLATE == {
        "ExportCompleted": "export_completed",
    }
    assert IDENTITY_EVENT_TO_TEMPLATE == {
        "UserPasswordChanged": "password_changed_confirmation",
    }
    assert "PasswordResetRequested" not in IDENTITY_EVENT_TO_TEMPLATE


def test_notification_context_shapes_are_stable():
    assert vendor_notification_context(
        business_name="Kigali Events",
        cta_url="https://linkapro.test/vendors/dashboard",
        reason="Add verification details.",
        client_name="Aline",
    ) == {
        "business_name": "Kigali Events",
        "cta_url": "https://linkapro.test/vendors/dashboard",
        "reason": "Add verification details.",
        "client_name": "Aline",
    }
    assert identity_notification_context(
        email="user@example.com",
        cta_url="https://linkapro.test/account/security",
    ) == {
        "email": "user@example.com",
        "cta_url": "https://linkapro.test/account/security",
    }
    assert payment_notification_context(
        payment_reference="pay_123",
        amount="15000",
        currency="RWF",
        status="success",
        cta_url="https://linkapro.test/payments/pay_123",
    ) == {
        "payment_reference": "pay_123",
        "amount": "15000",
        "currency": "RWF",
        "status": "success",
        "cta_url": "https://linkapro.test/payments/pay_123",
    }
    assert export_notification_context(
        event_name="Wedding",
        export_type="Timeline",
        file_url="https://cdn.test/timeline.pdf",
        cta_url="https://cdn.test/timeline.pdf",
    ) == {
        "event_name": "Wedding",
        "export_type": "Timeline",
        "file_url": "https://cdn.test/timeline.pdf",
        "cta_url": "https://cdn.test/timeline.pdf",
    }
