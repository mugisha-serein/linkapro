# DRF Serializer - Device

from rest_framework import serializers

class DeviceSerializer(serializers.Serializer):
    user_agent = serializers.CharField()
    fingerprint = serializers.CharField()
    device_type = serializers.CharField()
