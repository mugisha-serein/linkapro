"""Account lifecycle rules."""
from .account_errors import AccountCannotBeActivated


def ensure_account_can_be_activated(*, is_verified: bool) -> None:
    if not is_verified:
        raise AccountCannotBeActivated("Account must be verified before activation")
