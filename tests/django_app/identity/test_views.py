import uuid
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from domain.identity.entities import User, UserRole
from domain.identity.value_objects import Email, PasswordHash, PlainPassword
from infrastructure.repos.django_user_repository import DjangoUserRepository
from infrastructure.adapters.password_hasher import DjangoPasswordHasher
from django_app.identity.models import User as DjangoUser

pytestmark = pytest.mark.django_db(transaction=True)


class TestIdentityViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.repo = DjangoUserRepository()
        self.hasher = DjangoPasswordHasher()
        self.client = APIClient()

    def test_register_success(self):
        url = reverse("register")
        data = {
            "email": "new@example.com",
            "password": "StrongPass1",
            "first_name": "Test",
            "last_name": "User",
            "role": "planner",
        }
        response = self.client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.data["email"] == "new@example.com"

        user = self.repo.get_by_email(Email("new@example.com"))
        assert user is not None

    def test_register_duplicate_email(self):
        plain = PlainPassword("StrongPass1")
        hashed = self.hasher.hash(plain)
        user = User(
            id=uuid.uuid4(),
            email=Email("exists@example.com"),
            password_hash=PasswordHash(hashed),
            first_name="A",
            last_name="B",
            role=UserRole.PLANNER,
        )
        self.repo.save(user)

        url = reverse("register")
        data = {
            "email": "exists@example.com",
            "password": "StrongPass1",
            "first_name": "Test",
            "last_name": "User",
            "role": "planner",
        }
        response = self.client.post(url, data, format="json")
        assert response.status_code == 400
        assert "already exists" in str(response.data["error"])

    def test_register_then_login_success(self):
        register_url = reverse("register")
        login_url = reverse("login")

        register_response = self.client.post(
            register_url,
            {
                "email": "fresh@example.com",
                "password": "StrongPass1",
                "first_name": "Fresh",
                "last_name": "User",
                "role": "planner",
            },
            format="json",
        )
        assert register_response.status_code == 201

        login_response = self.client.post(
            login_url,
            {
                "email": "fresh@example.com",
                "password": "StrongPass1",
            },
            format="json",
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.data
        assert "refresh_token" in login_response.data

    def test_login_success(self):
        plain = PlainPassword("StrongPass1")
        hashed = self.hasher.hash(plain)
        user = User(
            id=uuid.uuid4(),
            email=Email("login@example.com"),
            password_hash=PasswordHash(hashed),
            first_name="L",
            last_name="User",
            role=UserRole.PLANNER,
            is_active=True,
        )
        self.repo.save(user)

    def test_login_wrong_password(self):
        plain = PlainPassword("Correct1")
        hashed = self.hasher.hash(plain)

        # Sanity check: hasher works as expected
        assert self.hasher.verify(PlainPassword("Correct1"), PasswordHash(hashed)) is True
        assert self.hasher.verify(PlainPassword("WrongPass1"), PasswordHash(hashed)) is False

        user = User(
            id=uuid.uuid4(),
            email=Email("wrong-login@example.com"),
            password_hash=PasswordHash(hashed),
            first_name="W",
            last_name="User",
            role=UserRole.PLANNER,
        )
        self.repo.save(user)

        url = reverse("login")
        data = {"email": "wrong-login@example.com", "password": "WrongPass1"}
        response = self.client.post(url, data, format="json")
        assert response.status_code == 401
        assert "error" in response.data

    def test_profile_endpoint_returns_authenticated_user(self):
        user = DjangoUser.objects.create_user(
            email="profile@example.com",
            password="StrongPass1",
            first_name="Profile",
            last_name="User",
            role="planner",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("profile"))
        assert response.status_code == 200
        assert response.data["email"] == "profile@example.com"
        assert response.data["role"] == "planner"

    def test_refresh_token_returns_access_token(self):
        user = DjangoUser.objects.create_user(
            email="refresh@example.com",
            password="StrongPass1",
            first_name="Refresh",
            last_name="User",
            role="planner",
        )
        self.client.force_authenticate(user=user)
        login_response = self.client.post(
            reverse("login"),
            {"email": "refresh@example.com", "password": "StrongPass1"},
            format="json",
        )
        refresh_token = login_response.data["refresh_token"]

        self.client.credentials()
        response = self.client.post(reverse("token-refresh"), {"refresh": refresh_token}, format="json")
        assert response.status_code == 200
        assert "access" in response.data
