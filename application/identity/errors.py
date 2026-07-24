class UserNotFoundError(ValueError):
    pass


class DuplicateUserError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InvalidTwoFactorCodeError(ValueError):
    pass
