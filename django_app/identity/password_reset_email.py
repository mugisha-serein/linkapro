import logging
import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from django_app.identity.models import PasswordResetEmailDelivery, User
from infrastructure.adapters.jwt_token_service import JWTTokenService

logger = logging.getLogger(__name__)

GENERIC_FORGOT_PASSWORD_DETAIL = "If an account exists for that email, password reset instructions have been sent."


def request_password_reset_email(email: str) -> bool:
    normalized_email = email.strip().lower()
    email_domain = _email_domain(normalized_email)
    masked_email = _mask_email(normalized_email)
    provider = _email_provider()
    logger.info(
        "forgot_password_requested",
        extra={"email_domain": email_domain, "masked_email": masked_email, "provider": provider},
    )

    user = User.objects.filter(email=normalized_email, is_active=True).first()

    if not user:
        logger.info(
            "forgot_password_email_skipped",
            extra={
                "email_domain": email_domain,
                "masked_email": masked_email,
                "provider": provider,
                "reason": "no_active_user",
            },
        )
        return False

    delivery = PasswordResetEmailDelivery.objects.create(
        user=user,
        email_hash=_email_hash(normalized_email),
        email_domain=email_domain,
        status=PasswordResetEmailDelivery.Status.QUEUED,
        provider=provider,
    )
    token = JWTTokenService().create_password_reset_token(str(user.id))
    logger.info(
        "forgot_password_email_dispatch_attempted",
        extra={
            "delivery_id": str(delivery.id),
            "user_id": str(user.id),
            "email_domain": email_domain,
            "masked_email": masked_email,
            "provider": provider,
        },
    )

    try:
        from tasks.email_tasks import send_password_reset_email_task

        send_password_reset_email_task.delay(str(user.id), token, str(delivery.id))
    except Exception as exc:
        _mark_delivery_deferred(delivery, exc)
        logger.error(
            "password_reset_email_dispatch_failed",
            extra={
                "delivery_id": str(delivery.id),
                "user_id": str(user.id),
                "email_domain": email_domain,
                "masked_email": masked_email,
                "provider": provider,
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        logger.error(
            "forgot_password_email_dispatch_deferred",
            extra={
                "delivery_id": str(delivery.id),
                "user_id": str(user.id),
                "email_domain": email_domain,
                "masked_email": masked_email,
                "provider": provider,
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        return False

    logger.info(
        "forgot_password_email_queued",
        extra={
            "delivery_id": str(delivery.id),
            "user_id": str(user.id),
            "email_domain": email_domain,
            "masked_email": masked_email,
            "provider": provider,
        },
    )
    return True


def send_password_reset_email(
    user_id: str,
    token: str,
    delivery_id: str | None = None,
    task_id: str | None = None,
    attempt: int = 1,
) -> bool:
    user = User.objects.filter(id=user_id, is_active=True).first()
    delivery = _get_delivery(delivery_id)
    if not user:
        if delivery:
            _mark_delivery_failed(delivery, "no_active_user", attempt)
        logger.info(
            "password_reset_email_failed",
            extra={
                "delivery_id": str(delivery.id) if delivery else None,
                "task_id": task_id,
                "user_id": str(user_id),
                "provider": delivery.provider if delivery else _email_provider(),
                "attempt": attempt,
                "reason": "no_active_user",
            },
        )
        return False

    email_domain = _email_domain(user.email)
    masked_email = _mask_email(user.email)
    provider = delivery.provider if delivery else _email_provider()
    logger.info(
        "password_reset_email_send_started",
        extra={
            "delivery_id": str(delivery.id) if delivery else None,
            "task_id": task_id,
            "user_id": str(user.id),
            "email_domain": email_domain,
            "masked_email": masked_email,
            "provider": provider,
            "attempt": attempt,
        },
    )
    try:
        reset_url = build_password_reset_url(token)
        send_mail(
            subject="Reset your LinkaPro password",
            message=build_password_reset_text(reset_url),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=build_password_reset_html(reset_url),
        )
    except Exception as exc:
        if delivery:
            _mark_delivery_failed(delivery, exc.__class__.__name__, attempt)
        logger.error(
            "password_reset_email_failed",
            extra={
                "delivery_id": str(delivery.id) if delivery else None,
                "task_id": task_id,
                "user_id": str(user.id),
                "email_domain": email_domain,
                "masked_email": masked_email,
                "provider": provider,
                "attempt": attempt,
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        raise

    if delivery:
        _mark_delivery_sent(delivery, attempt)

    logger.info(
        "password_reset_email_sent",
        extra={
            "delivery_id": str(delivery.id) if delivery else None,
            "task_id": task_id,
            "user_id": str(user.id),
            "email_domain": email_domain,
            "masked_email": masked_email,
            "provider": provider,
            "attempt": attempt,
        },
    )
    return True


def build_password_reset_url(token: str) -> str:
    frontend_url = _frontend_url()
    return f"{frontend_url}/auth/reset-password?token={token}"


def build_password_reset_text(reset_url: str) -> str:
    expiration = _format_timeout(settings.PASSWORD_RESET_TIMEOUT)
    return "\n".join(
        [
            "LinkaPro password reset request",
            "",
            "Use this link to reset your password:",
            reset_url,
            "",
            f"This link expires in {expiration}.",
            "If you did not request a password reset, you can safely ignore this email.",
        ]
    )


def build_password_reset_html(reset_url: str) -> str:
    expiration = _format_timeout(settings.PASSWORD_RESET_TIMEOUT)
    return (
        "<p>LinkaPro password reset request</p>"
        f'<p><a href="{reset_url}">Reset your password</a></p>'
        f"<p>This link expires in {expiration}.</p>"
        "<p>If you did not request a password reset, you can safely ignore this email.</p>"
    )


def _frontend_url() -> str:
    frontend_url = (getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")
    if not frontend_url:
        logger.error(
            "email_backend_misconfigured",
            extra={"reason": "frontend_url_missing", "provider": _email_provider()},
        )
        raise ValueError("FRONTEND_URL is not configured")
    if not settings.DEBUG and not frontend_url.lower().startswith("https://"):
        logger.error(
            "email_backend_misconfigured",
            extra={"reason": "frontend_url_not_https", "provider": _email_provider()},
        )
        raise ValueError("FRONTEND_URL must use HTTPS in production")
    return frontend_url


def _format_timeout(timeout: timedelta) -> str:
    total_seconds = int(timeout.total_seconds())
    if total_seconds % 3600 == 0:
        hours = total_seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    minutes = max(1, total_seconds // 60)
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def _email_domain(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].lower()


def _email_hash(email: str) -> str:
    secret = str(settings.SECRET_KEY).encode("utf-8")
    normalized_email = email.strip().lower().encode("utf-8")
    return hmac.new(secret, normalized_email, hashlib.sha256).hexdigest()


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local_part, domain = email.rsplit("@", 1)
    prefix = local_part[:1] if local_part else "*"
    return f"{prefix}***@{domain.lower()}"


def _email_provider() -> str:
    backend = (getattr(settings, "EMAIL_BACKEND", "") or "").strip()
    if not backend:
        return "django_email_backend"
    return backend.rsplit(".", 1)[-1] or "django_email_backend"


def _get_delivery(delivery_id: str | None) -> PasswordResetEmailDelivery | None:
    if not delivery_id:
        return None
    return PasswordResetEmailDelivery.objects.filter(id=delivery_id).first()


def _mark_delivery_deferred(delivery: PasswordResetEmailDelivery, exc: Exception) -> None:
    delivery.status = PasswordResetEmailDelivery.Status.DEFERRED
    delivery.failure_reason = exc.__class__.__name__[:255]
    delivery.failed_at = timezone.now()
    delivery.save(update_fields=["status", "failure_reason", "failed_at", "updated_at"])


def _mark_delivery_failed(delivery: PasswordResetEmailDelivery, reason: str, attempt: int) -> None:
    delivery.status = PasswordResetEmailDelivery.Status.FAILED
    delivery.failure_reason = reason[:255]
    delivery.attempts = max(delivery.attempts + 1, attempt)
    delivery.failed_at = timezone.now()
    delivery.save(update_fields=["status", "failure_reason", "attempts", "failed_at", "updated_at"])


def _mark_delivery_sent(delivery: PasswordResetEmailDelivery, attempt: int) -> None:
    delivery.status = PasswordResetEmailDelivery.Status.SENT
    delivery.failure_reason = ""
    delivery.attempts = max(delivery.attempts + 1, attempt)
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=["status", "failure_reason", "attempts", "sent_at", "updated_at"])
