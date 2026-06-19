import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail

from django_app.identity.models import User
from infrastructure.adapters.jwt_token_service import JWTTokenService

logger = logging.getLogger(__name__)

GENERIC_FORGOT_PASSWORD_DETAIL = "If an account exists for that email, password reset instructions have been sent."


def request_password_reset_email(email: str) -> bool:
    normalized_email = email.strip().lower()
    email_domain = _email_domain(normalized_email)
    user = User.objects.filter(email=normalized_email, is_active=True).first()

    if not user:
        logger.info(
            "forgot_password_email_skipped",
            extra={"email_domain": email_domain, "reason": "no_active_user"},
        )
        return False

    token = JWTTokenService().create_password_reset_token(str(user.id))
    logger.info(
        "forgot_password_email_queued",
        extra={"user_id": str(user.id), "email_domain": email_domain},
    )

    try:
        from tasks.email_tasks import send_password_reset_email_task

        send_password_reset_email_task.delay(str(user.id), token)
    except Exception as exc:
        logger.error(
            "forgot_password_email_dispatch_deferred",
            extra={
                "user_id": str(user.id),
                "email_domain": email_domain,
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        return False

    return True


def send_password_reset_email(user_id: str, token: str) -> bool:
    user = User.objects.filter(id=user_id, is_active=True).first()
    if not user:
        logger.info("forgot_password_email_skipped", extra={"user_id": str(user_id), "reason": "no_active_user"})
        return False

    email_domain = _email_domain(user.email)
    reset_url = build_password_reset_url(token)
    send_mail(
        subject="Reset your LinkaPro password",
        message=build_password_reset_text(reset_url),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=build_password_reset_html(reset_url),
    )

    logger.info(
        "forgot_password_email_sent",
        extra={"user_id": str(user.id), "email_domain": email_domain},
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
        raise ValueError("FRONTEND_URL is not configured")
    if not settings.DEBUG and not frontend_url.lower().startswith("https://"):
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
