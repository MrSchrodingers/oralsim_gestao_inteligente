"""Tests for authentication and JWT tokens."""

from django.test import TestCase
from django.urls import reverse

from oralsin_core.adapters.security.hash_service import HashService
from oralsin_core.adapters.security.jwt_service import JWTService
from plugins.django_interface.models import Clinic, User, UserClinic
from config import settings


class AuthTokenTests(TestCase):
    def test_clinic_login_returns_clinic_token(self) -> None:
        clinic = Clinic.objects.create(oralsin_clinic_id=999, name="Test Clinic")
        password = "secret123"
        user = User.objects.create(
            email="clinic@example.com",
            password_hash=HashService.hash_password(password),
            name="Clinic User",
            role="clinic",
        )
        UserClinic.objects.create(user=user, clinic=clinic)

        url = reverse("login")
        resp = self.client.post(url, {"email": user.email, "password": password})
        self.assertEqual(resp.status_code, 200)
        cookie = resp.cookies.get(settings.AUTH_COOKIE_NAME)
        self.assertIsNotNone(cookie, "JWT cookie não encontrado")
        payload = JWTService.decode_token(cookie.value)
        self.assertEqual(payload["sub"], str(user.id))
        self.assertEqual(payload.get("clinic"), str(clinic.id))