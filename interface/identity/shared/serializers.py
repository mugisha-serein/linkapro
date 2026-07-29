from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from application.identity.account.register_account_command import RegisterUserCommand
from application.identity.authentication.login_with_password_command import LoginUserCommand
from application.identity.authorization.assign_role_command import AssignRoleCommand
from application.identity.authorization.reactivate_account_command import ReactivateAccountCommand
from application.identity.authorization.suspend_account_command import SuspendAccountCommand
from application.identity.authorization.unlock_account_command import UnlockAccountCommand
from application.identity.credentials.change_password_command import ChangePasswordCommand
from application.identity.mfa.generate_recovery_codes import GenerateRecoveryCodesCommand
from application.identity.mfa.regenerate_recovery_codes import RegenerateRecoveryCodesCommand
from application.identity.recovery.reset_password_command import (
    PasswordResetTokenInput,
    ResetPasswordCommand,
    SecurityMetadataHash,
)
from domain.identity.account import AccountRole
from domain.identity.credentials import Email, PasswordPolicy, PlainPassword
from domain.identity.shared.security_reason import InvalidSecurityReasonError, SecurityReason
from domain.identity.verification import VerificationCode


def validate_plain_password(value):
    try:
        plain_password = PlainPassword(value)
        PasswordPolicy.validate(plain_password)
        validate_password(value)
    except DjangoValidationError as e:
        raise serializers.ValidationError(list(e.messages))
    except Exception as e:
        raise serializers.ValidationError(str(e))
    return value


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=["planner", "vendor"])

    def validate_email(self, value):
        try:
            Email(value)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate_password(self, value):
        return validate_plain_password(value)

    def to_command(self) -> RegisterUserCommand:
        return RegisterUserCommand(
            email=Email(self.validated_data["email"]),
            plain_password=PlainPassword(self.validated_data["password"]),
            first_name=self.validated_data["first_name"],
            last_name=self.validated_data["last_name"],
            role=AccountRole(self.validated_data["role"]),
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def to_command(self) -> LoginUserCommand:
        return LoginUserCommand(
            email=Email(self.validated_data["email"]),
            plain_password=PlainPassword(self.validated_data["password"]),
        )


class TwoFactorLoginSerializer(serializers.Serializer):
    temp_token = serializers.CharField()
    token = serializers.CharField(min_length=6, max_length=6)

    def to_command(self):
        from application.identity.authentication.complete_mfa_login_command import LoginTwoFactorCommand

        return LoginTwoFactorCommand(
            temp_token=self.validated_data["temp_token"],
            token=VerificationCode(self.validated_data["token"]),
        )


class TwoFactorSetupVerifySerializer(serializers.Serializer):
    token = serializers.CharField(min_length=6, max_length=6)

    def verification_code(self) -> VerificationCode:
        return VerificationCode(self.validated_data["token"])


class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)


class AssignRoleSerializer(serializers.Serializer):
    new_role = serializers.ChoiceField(choices=[role.value for role in AccountRole])
    reason = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)

    def validate_reason(self, value):
        try:
            return SecurityReason(value)
        except InvalidSecurityReasonError as exc:
            raise serializers.ValidationError(str(exc))

    def to_command(self, *, actor_id, target_user_id) -> AssignRoleCommand:
        reason = self.validated_data.get("reason")
        return AssignRoleCommand(
            actor_id=actor_id,
            target_user_id=target_user_id,
            new_role=AccountRole(self.validated_data["new_role"]),
            reason=reason,
        )


class SuspendAccountSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)

    def validate_reason(self, value):
        try:
            return SecurityReason(value)
        except InvalidSecurityReasonError as exc:
            raise serializers.ValidationError(str(exc))

    def to_command(self, *, actor_id, target_user_id) -> SuspendAccountCommand:
        return SuspendAccountCommand(
            actor_id=actor_id,
            target_user_id=target_user_id,
            reason=self.validated_data["reason"],
        )


class OptionalReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)


class ReactivateAccountSerializer(OptionalReasonSerializer):
    def to_command(self, *, actor_id, target_user_id) -> ReactivateAccountCommand:
        return ReactivateAccountCommand(
            actor_id=actor_id,
            target_user_id=target_user_id,
            reason=self.validated_data.get("reason"),
        )


class UnlockAccountSerializer(OptionalReasonSerializer):
    def to_command(self, *, actor_id, target_user_id) -> UnlockAccountCommand:
        return UnlockAccountCommand(
            actor_id=actor_id,
            target_user_id=target_user_id,
            reason=self.validated_data.get("reason"),
        )


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        return validate_plain_password(value)

    def to_command(self, *, user_id) -> ChangePasswordCommand:
        return ChangePasswordCommand(
            user_id=user_id,
            current_password=PlainPassword(self.validated_data["current_password"]),
            new_password=PlainPassword(self.validated_data["new_password"]),
        )


class RecoveryCodesSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, min_value=1, max_value=20, default=10)

    def to_generate_command(self, *, user_id) -> GenerateRecoveryCodesCommand:
        return GenerateRecoveryCodesCommand(
            user_id=user_id,
            count=self.validated_data["count"],
        )

    def to_regenerate_command(self, *, user_id) -> RegenerateRecoveryCodesCommand:
        return RegenerateRecoveryCodesCommand(
            user_id=user_id,
            count=self.validated_data["count"],
        )


class SetupPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_password(self, value):
        return validate_plain_password(value)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(required=False)
    reset_token = serializers.CharField(required=False)
    new_password = serializers.CharField(write_only=True, min_length=8, required=False)
    password = serializers.CharField(write_only=True, min_length=8, required=False)

    def validate(self, attrs):
        token = attrs.get("token") or attrs.get("reset_token")
        password = attrs.get("new_password") or attrs.get("password")
        if not token:
            raise serializers.ValidationError({"token": "This field is required."})
        if not password:
            raise serializers.ValidationError({"new_password": "This field is required."})
        try:
            validate_plain_password(password)
        except serializers.ValidationError as e:
            raise serializers.ValidationError({"new_password": e.detail})
        attrs["token"] = token
        attrs["new_password"] = password
        return attrs

    def to_command(self, *, client_ip_hash: str, user_agent_hash: str) -> ResetPasswordCommand:
        return ResetPasswordCommand(
            token=PasswordResetTokenInput(self.validated_data["token"]),
            new_password=PlainPassword(self.validated_data["new_password"]),
            client_ip_hash=SecurityMetadataHash(client_ip_hash),
            user_agent_hash=SecurityMetadataHash(user_agent_hash),
        )
