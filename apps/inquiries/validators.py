import requests
from django.conf import settings
from rest_framework import serializers

RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'
HCAPTCHA_VERIFY_URL = 'https://hcaptcha.com/siteverify'


def _format_error_message(provider, payload):
    errors = payload.get('error-codes') or payload.get('errors') or []
    if not isinstance(errors, list):
        errors = [errors]
    if errors:
        return f'{provider} verification failed: {", ".join(errors)}'
    return f'{provider} verification failed.'


def validate_captcha_token(token, provider='recaptcha', remoteip=None, expected_action=None):
    if not token:
        raise serializers.ValidationError({'captcha_token': 'Captcha token is required.'})

    provider = provider.lower()
    if provider == 'hcaptcha':
        secret = getattr(settings, 'HCAPTCHA_SECRET_KEY', '')
        verify_url = HCAPTCHA_VERIFY_URL
    elif provider == 'recaptcha':
        secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')
        verify_url = RECAPTCHA_VERIFY_URL
    else:
        raise serializers.ValidationError({'captcha_provider': 'Unsupported captcha provider.'})

    if not secret:
        raise serializers.ValidationError({'captcha_provider': 'Captcha secret key is not configured.'})

    payload = {
        'secret': secret,
        'response': token,
    }
    if remoteip:
        payload['remoteip'] = remoteip

    try:
        response = requests.post(verify_url, data=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        raise serializers.ValidationError({'captcha_token': 'Unable to verify captcha at this time.'})

    if not result.get('success'):
        raise serializers.ValidationError({'captcha_token': _format_error_message(provider, result)})

    if provider == 'recaptcha':
        score = result.get('score')
        threshold = getattr(settings, 'CAPTCHA_RECAPTCHA_SCORE_THRESHOLD', 0.5)
        if score is None or float(score) < float(threshold):
            raise serializers.ValidationError({
                'captcha_token': 'reCAPTCHA score is too low. Please try again.'
            })
        if expected_action and result.get('action') != expected_action:
            raise serializers.ValidationError({
                'captcha_token': 'reCAPTCHA action mismatch.'
            })

    return result
