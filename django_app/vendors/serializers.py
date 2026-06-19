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
    custom_category = serializers.CharField(max_length=120, required=False, allow_blank=True, allow_null=True)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        category = attrs.get("category")
        custom_category = (attrs.get("custom_category") or "").strip()
        if category == "other" and not custom_category:
            raise serializers.ValidationError({"custom_category": ["Tell us what service you provide when choosing Other."]})
        if category and category != "other":
            attrs["custom_category"] = None
        elif custom_category:
            attrs["custom_category"] = custom_category
        return attrs

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
    package_tier = serializers.ChoiceField(choices=["standard", "premier", "gold"])

class InquirySerializer(serializers.Serializer):
    client_name = serializers.CharField(max_length=200)
    client_email = serializers.EmailField()
    client_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    message = serializers.CharField()
    event_date = serializers.DateField(required=False, allow_null=True)


class VerificationDocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=[
        "business_registration",
        "tax_certificate",
        "trade_license",
        "owner_id",
        "other",
    ])
    document = serializers.FileField()
