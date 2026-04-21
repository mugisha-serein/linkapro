from rest_framework import serializers

class FlagContentSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=["vendor_profile", "review", "portfolio_image"])
    content_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=500)