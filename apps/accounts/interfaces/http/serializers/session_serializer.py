# DRF Serializer - Session

from rest_framework import serializers

class SessionSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    device_id = serializers.CharField()
