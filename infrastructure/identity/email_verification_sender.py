"""Email verification sender adapter."""

from application.identity.shared.ports import EmailVerificationSender
from domain.identity.verification import EmailVerificationToken
from tasks.notifications import send_email_task


class DjangoEmailVerificationSender(EmailVerificationSender):
    def send_email_verification(self, *, to: str, token: EmailVerificationToken) -> None:
        send_email_task.delay(
            to=to,
            template="email_verification",
            context={"token": token.reveal_for_email_verification()},
        )


__all__ = ["DjangoEmailVerificationSender"]
