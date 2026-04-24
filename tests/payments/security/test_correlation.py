import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from payments.infrastructure.correlation_middleware import CorrelationMiddleware, get_correlation_id


def test_correlation_id_propagation(client):
    """Header should be passed through when provided."""
    response = client.get('/admin/', HTTP_X_CORRELATION_ID='test-cid')
    assert response['X-Correlation-ID'] == 'test-cid'


def test_correlation_id_generated_if_missing(client):
    """Header should be generated if not provided."""
    response = client.get('/admin/')
    assert 'X-Correlation-ID' in response
    assert len(response['X-Correlation-ID']) > 0


def test_thread_local_storage():
    """Thread-local should store correlation ID during request processing."""
    request = RequestFactory().get('/')
    # Use a real HttpResponse as the response from the next middleware/view
    middleware = CorrelationMiddleware(lambda r: HttpResponse())
    middleware(request)
    # After middleware runs, the thread-local should still hold the ID
    # (it's cleared only when the middleware finishes, but the test can check it here)
    # Actually, the middleware stores it before calling get_response, so we can check after
    cid = get_correlation_id()
    assert cid is not None