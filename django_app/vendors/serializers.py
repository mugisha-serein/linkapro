from rest_framework import serializers

from .models import PortfolioImage, ServicePackage, VendorProfile

PRIVATE_PORTFOLIO_URL_MARKERS = ("vendor_portfolio_uploads",)
PRIVATE_PORTFOLIO_URL_PREFIXES = ("/media/",)


def is_safe_public_portfolio_url(url: str | None) -> bool:
    if not url:
        return False
    value = str(url).strip()
    if not value:
        return False
    if value.startswith(PRIVATE_PORTFOLIO_URL_PREFIXES):
        return False
    if any(marker in value for marker in PRIVATE_PORTFOLIO_URL_MARKERS):
        return False
    return True


def public_portfolio_display_url(obj: PortfolioImage) -> str | None:
    for url in (obj.cloudinary_secure_url, obj.secure_url):
        if is_safe_public_portfolio_url(url):
            return str(url).strip()
    return None


def safe_public_branding_url(url: str | None) -> str | None:
    if not url:
        return None
    value = str(url).strip()
    if not value or not value.startswith("https://"):
        return None
    if value.startswith(PRIVATE_PORTFOLIO_URL_PREFIXES):
        return None
    if any(marker in value for marker in PRIVATE_PORTFOLIO_URL_MARKERS):
        return None
    return value


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
    pass

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
    currency = serializers.ChoiceField(choices=["RWF"], default="RWF")
    package_tier = serializers.ChoiceField(choices=["standard", "premier", "gold"])

class InquirySerializer(serializers.Serializer):
    client_name = serializers.CharField(max_length=200)
    client_email = serializers.EmailField()
    client_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    message = serializers.CharField(min_length=10, max_length=5000)
    event_date = serializers.DateField(required=False, allow_null=True)


class VendorPublicPortfolioItemSerializer(serializers.ModelSerializer):
    display_url = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioImage
        fields = ("id", "media_type", "display_url", "caption", "width", "height", "duration_seconds")

    def get_display_url(self, obj):
        return public_portfolio_display_url(obj)


class VendorPublicPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePackage
        fields = ("id", "name", "description", "price", "currency", "package_tier")


class VendorPublicReviewSummarySerializer(serializers.Serializer):
    average_rating = serializers.FloatField()
    total_reviews = serializers.IntegerField()


class VendorPublicProfileSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display")
    custom_category = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    portfolio = serializers.SerializerMethodField()
    packages = serializers.SerializerMethodField()
    reviews_summary = serializers.SerializerMethodField()

    class Meta:
        model = VendorProfile
        fields = (
            "id", "business_name", "category", "category_label", "custom_category",
            "description", "service_area", "website", "profile_image_url", "cover_image_url", "is_verified",
            "average_rating", "total_reviews", "portfolio", "packages", "reviews_summary",
        )

    def get_custom_category(self, obj):
        return obj.custom_category if obj.category == VendorProfile.Category.OTHER else None

    def get_profile_image_url(self, obj):
        return safe_public_branding_url(obj.profile_image_url)

    def get_cover_image_url(self, obj):
        cover_image_url = safe_public_branding_url(obj.cover_image_url)
        if cover_image_url:
            return cover_image_url
        for item in getattr(obj, "public_portfolio", []):
            display_url = public_portfolio_display_url(item)
            if display_url:
                return display_url
        return None

    def get_is_verified(self, obj):
        return obj.status == VendorProfile.Status.APPROVED

    def get_average_rating(self, obj):
        return float(self.context.get("average_rating", 0))

    def get_total_reviews(self, obj):
        return int(self.context.get("total_reviews", 0))

    def get_portfolio(self, obj):
        portfolio = [
            item
            for item in getattr(obj, "public_portfolio", [])
            if public_portfolio_display_url(item)
        ]
        return VendorPublicPortfolioItemSerializer(portfolio, many=True).data

    def get_packages(self, obj):
        return VendorPublicPackageSerializer(getattr(obj, "public_packages", []), many=True).data

    def get_reviews_summary(self, obj):
        return VendorPublicReviewSummarySerializer(
            {"average_rating": self.get_average_rating(obj), "total_reviews": self.get_total_reviews(obj)}
        ).data


class VerificationDocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=[
        "business_registration",
        "tax_certificate",
        "trade_license",
        "owner_id",
        "other",
    ])
    document = serializers.FileField()
