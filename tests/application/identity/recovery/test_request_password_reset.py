from application.identity.recovery import RequestPasswordResetUseCase


class FakeGateway:
    def __init__(self, queued=True):
        self.queued = queued
        self.email = None

    def request_password_reset(self, email: str) -> bool:
        self.email = email
        return self.queued


def test_request_password_reset_normalizes_email_and_returns_result():
    gateway = FakeGateway(queued=True)

    result = RequestPasswordResetUseCase(gateway=gateway).execute(
        email="  User@Example.COM  ",
    )

    assert result.queued is True
    assert gateway.email == "user@example.com"


def test_request_password_reset_preserves_generic_false_result():
    gateway = FakeGateway(queued=False)

    result = RequestPasswordResetUseCase(gateway=gateway).execute(
        email="missing@example.com",
    )

    assert result.queued is False
    assert gateway.email == "missing@example.com"
