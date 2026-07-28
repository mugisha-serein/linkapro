"""Django gateway for requesting password reset delivery."""

from django_app.identity.password_reset_email import request_password_reset_email


class DjangoPasswordResetRequestGateway:
    def request_password_reset(self, email: str) -> bool:
        return request_password_reset_email(email)


__all__ = ["DjangoPasswordResetRequestGateway"]
