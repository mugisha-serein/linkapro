import json
from django.http import JsonResponse, HttpResponseBadRequest
from payments.infrastructure.jwe_adapter import JweEnvelopeAdapter

class JweMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.adapter = JweEnvelopeAdapter()

    def __call__(self, request):
        if request.method == 'POST' and request.path.endswith('/initiate/'):
            if request.content_type == 'application/jose':
                try:
                    decrypted = self.adapter.decrypt_request(request.body.decode('utf-8'))
                    # Replace request body with decrypted data (mimic DRF)
                    request._body = json.dumps(decrypted).encode('utf-8')
                    request._stream = None  # reset to allow parsing
                except ValueError:
                    return HttpResponseBadRequest("Invalid JWE payload")
        response = self.get_response(request)
        # If response is successful and client sent JWE, encrypt response
        if response.status_code == 200 and request.META.get('HTTP_ACCEPT') == 'application/jose':
            try:
                # Client must have sent its public key in custom header for response encryption
                client_jwk = json.loads(request.headers.get('X-Client-JWK', '{}'))
                if client_jwk:
                    response_data = json.loads(response.content)
                    encrypted = self.adapter.encrypt_response(response_data, client_jwk)
                    return JsonResponse(encrypted, safe=False, status=response.status_code)
            except Exception:
                pass  # fallback to plain JSON
        return response