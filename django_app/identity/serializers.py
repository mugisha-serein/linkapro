from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from application.identity.commands import RegisterUserCommand, LoginUserCommand
from domain.identity.value_objects import Email, PlainPassword


def validate_plain_password(value):
    try:
        PlainPassword(value)
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
            role=self.validated_data["role"],
        )

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def to_command(self) -> LoginUserCommand:
        return LoginUserCommand(
            email=Email(self.validated_data["email"]),
            plain_password=self.validated_data["password"],
        )
    
class TwoFactorLoginSerializer(serializers.Serializer):
    temp_token = serializers.CharField()
    token = serializers.CharField(min_length=6, max_length=6)


class TwoFactorSetupVerifySerializer(serializers.Serializer):
    token = serializers.CharField(min_length=6, max_length=6)


class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)


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
