from __future__ import annotations


VENDOR_EVENT_TO_TEMPLATE = {
    "VendorSubmittedForReview": "vendor_submitted_for_review",
    "VendorApproved": "vendor_approved",
    "VendorRejected": "vendor_rejected",
    "VendorSuspended": "vendor_suspended",
    "VendorReinstated": "vendor_reinstated",
    "VendorProfileUpdated": "vendor_profile_updated",
    "InquiryReceived": "inquiry_received",
}
PAYMENT_EVENT_TO_TEMPLATE = {
    "PaymentCompleted": "payment_completed",
    "PaymentExpired": "payment_expired",
}
DOCUMENT_EVENT_TO_TEMPLATE = {
    "ExportCompleted": "export_completed",
}
IDENTITY_EVENT_TO_TEMPLATE = {
    "UserPasswordChanged": "password_changed_confirmation",
}


def vendor_notification_context(
    *,
    business_name: str,
    cta_url: str,
    reason: str | None = None,
    client_name: str | None = None,
) -> dict:
    context = {
        "business_name": business_name,
        "cta_url": cta_url,
    }
    if reason:
        context["reason"] = reason
    if client_name:
        context["client_name"] = client_name
    return context


def identity_notification_context(*, email: str, cta_url: str) -> dict:
    return {
        "email": email,
        "cta_url": cta_url,
    }


def payment_notification_context(
    *,
    payment_reference: str,
    amount: str,
    currency: str,
    status: str,
    cta_url: str,
) -> dict:
    return {
        "payment_reference": payment_reference,
        "amount": amount,
        "currency": currency,
        "status": status,
        "cta_url": cta_url,
    }


def export_notification_context(
    *,
    event_name: str,
    export_type: str,
    file_url: str,
    cta_url: str,
) -> dict:
    return {
        "event_name": event_name,
        "export_type": export_type,
        "file_url": file_url,
        "cta_url": cta_url,
    }
