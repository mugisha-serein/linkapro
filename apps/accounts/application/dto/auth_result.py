# DTO - Auth Result

class AuthResult:
    def __init__(self, success: bool, user_id: str = None, error: str = None):
        self.success = success
        self.user_id = user_id
        self.error = error

    @classmethod
    def success(cls, user_id: str):
        return cls(True, user_id=user_id)

    @classmethod
    def failure(cls, error: str):
        return cls(False, error=error)
