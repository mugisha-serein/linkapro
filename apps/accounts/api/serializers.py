from rest_framework import serializers
from dj_rest_auth.serializers import UserDetailsSerializer
from ..models import User
from ..services.registration_service import (
    register_planner,
    register_vendor,
    create_admin_user,
)
from ..validators.password import validate_password_policy


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model - used for registration and profile endpoints"""
    
    class Meta:
        model = User
        fields = ('id', 'email', 'role', 'is_active', 'is_verified', 'date_joined')
        read_only_fields = ('id', 'date_joined', 'is_active')


class PlannerRegistrationSerializer(serializers.Serializer):
    """Serializer for Planner registration"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=12)
    password_confirm = serializers.CharField(write_only=True, min_length=12)
    full_name = serializers.CharField(required=False, allow_blank=True)

    def validate_password(self, value):
        validate_password_policy(value)
        return value

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        full_name = validated_data.pop('full_name', '')
        return register_planner(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=full_name,
        )


class VendorRegistrationSerializer(serializers.Serializer):
    """Serializer for Vendor registration"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=12)
    password_confirm = serializers.CharField(write_only=True, min_length=12)
    business_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)

    def validate_password(self, value):
        validate_password_policy(value)
        return value

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        return register_vendor(
            email=validated_data['email'],
            password=validated_data['password'],
            business_name=validated_data.get('business_name', ''),
            phone=validated_data.get('phone', ''),
            location=validated_data.get('location', ''),
        )


class AdminCreationSerializer(serializers.Serializer):
    """Serializer for Admin creation (internal use only)"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=12)
    password_confirm = serializers.CharField(write_only=True, min_length=12)

    def validate_password(self, value):
        validate_password_policy(value)
        return value

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        return create_admin_user(
            email=validated_data['email'],
            password=validated_data['password'],
        )


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset"""
    email = serializers.EmailField()

    def validate_email(self, value):
        # Do not reveal whether an email exists in the system.
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset with token"""
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=12)
    new_password_confirm = serializers.CharField(write_only=True, min_length=12)

    def validate_new_password(self, value):
        validate_password_policy(value)
        return value

    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match'})
        return data