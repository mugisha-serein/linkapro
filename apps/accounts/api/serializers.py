from rest_framework import serializers
from dj_rest_auth.serializers import UserDetailsSerializer
from ..models import User
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
        user = User.objects.create_planner(
            email=validated_data['email'],
            password=validated_data['password']
        )
        # Update planner profile with full_name if provided
        if full_name and hasattr(user, 'planner_profile'):
            user.planner_profile.full_name = full_name
            user.planner_profile.save()
        return user


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
        user = User.objects.create_vendor(
            email=validated_data['email'],
            password=validated_data['password'],
            business_name=validated_data.get('business_name', ''),
            phone=validated_data.get('phone', ''),
            location=validated_data.get('location', '')
        )
        return user


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
        user = User.objects.create_admin(
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


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