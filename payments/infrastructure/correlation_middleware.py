import uuid
import threading
from django.conf import settings

_local = threading.local()

def get_correlation_id():
    return getattr(_local, 'correlation_id', None)

def set_correlation_id(cid):
    _local.correlation_id = cid

class CorrelationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = request.headers.get('X-Correlation-ID') or str(uuid.uuid4())
        set_correlation_id(cid)
        request.correlation_id = cid
        response = self.get_response(request)
        response['X-Correlation-ID'] = cid
        return response