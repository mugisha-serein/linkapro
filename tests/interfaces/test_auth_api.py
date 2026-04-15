# Interface Layer API Test - Auth Endpoints
import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_login_endpoint():
    client = APIClient()
    response = client.post('/auth/login/', {'email': 'test@example.com', 'password': 'password'})
    assert response.status_code in (200, 400, 401)
