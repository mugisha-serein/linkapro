from rest_framework import serializers
from application.identity.commands import RegisterUserCommand, LoginUserCommand
from domain.identity.value_objects import Email, PlainPassword

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
        try:
            PlainPassword(value)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return value

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
    password = serializers.CharField(write_only=True)

    def to_command(self) -> LoginUserCommand:
        return LoginUserCommand(
            email=Email(self.validated_data["email"]),
            plain_password=PlainPassword(self.validated_data["password"]),
        )
    
class TwoFactorLoginSerializer(serializers.Serializer):
    temp_token = serializers.CharField()
    token = serializers.CharField(min_length=6, max_length=6)


class TwoFactorSetupVerifySerializer(serializers.Serializer):
    token = serializers.CharField(min_length=6, max_length=6)


class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)