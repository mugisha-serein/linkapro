import json
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from jwcrypto import jwk, jwe as jwe_lib
from unittest.mock import patch

from payments.infrastructure.jwe_adapter import JweEnvelopeAdapter

pytestmark = pytest.mark.django_db


class TestJweEndToEnd:
    @pytest.fixture
    def jwe_key(self, settings):
        key = jwk.JWK.generate(kty='EC', crv='P-256')
        settings.JWE_PRIVATE_KEY = key.export_to_pem().decode()
        return key

    @patch("payments.infrastructure.middleware.HmacRequestValidator._validate_request", return_value=None)
    def test_public_key_endpoint(self, mock_validate, client, jwe_key):
        url = reverse("payments:payment-public-key")
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "kty" in data

    def test_encrypt_decrypt_roundtrip(self, settings, jwe_key):
        settings.JWE_PRIVATE_KEY = jwe_key.export_to_pem().decode()
        adapter = JweEnvelopeAdapter()
        original = {"amount": "1000", "currency": "RWF"}

        # Use the adapter for both encryption and decryption to avoid mismatches
        server_pub_jwk = adapter.get_public_jwk()
        jwe_compact = adapter.encrypt_response(original, server_pub_jwk)
        decrypted = adapter.decrypt_request(jwe_compact)
        assert decrypted == original