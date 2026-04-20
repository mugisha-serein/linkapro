from rest_framework import serializers

class VendorProfileSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=200)
    category = serializers.ChoiceField(choices=[
        "photography", "catering", "decor", "venue",
        "entertainment", "transportation", "attire", "other"
    ])
    description = serializers.CharField()
    service_area = serializers.CharField(max_length=200)
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(max_length=30)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)

class SubmitForReviewSerializer(serializers.Serializer):
    pass  # No fields needed

class PortfolioImageSerializer(serializers.Serializer):
    caption = serializers.CharField(required=False, allow_blank=True)

class ReorderImagesSerializer(serializers.Serializer):
    image_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False
    )

class ServicePackageSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3, default="RWF")

class InquirySerializer(serializers.Serializer):
    client_name = serializers.CharField(max_length=200)
    client_email = serializers.EmailField()
    client_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    message = serializers.CharField()
    event_date = serializers.DateField(required=False, allow_null=True)