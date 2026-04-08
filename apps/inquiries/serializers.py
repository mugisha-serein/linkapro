from rest_framework import serializers
from .models import Inquiry
from .validators import validate_captcha_token


class InquirySerializer(serializers.ModelSerializer):
    captcha_token = serializers.CharField(write_only=True)
    captcha_provider = serializers.ChoiceField(
        choices=(('recaptcha', 'reCAPTCHA v3'), ('hcaptcha', 'hCaptcha')),
        default='recaptcha',
        write_only=True,
    )

    class Meta:
        model = Inquiry
        fields = (
            'id',
            'name',
            'email',
            'subject',
            'message',
            'captcha_token',
            'captcha_provider',
            'created_at',
        )
        read_only_fields = ('id', 'created_at')

    def validate(self, attrs):
        request = self.context.get('request')
        token = attrs.get('captcha_token')
        provider = attrs.get('captcha_provider', 'recaptcha')
        remoteip = None
        if request is not None:
            remoteip = request.META.get('REMOTE_ADDR')

        validate_captcha_token(token, provider=provider, remoteip=remoteip, expected_action='inquiry')
        return attrs

    def create(self, validated_data):
        validated_data.pop('captcha_token', None)
        return super().create(validated_data)
