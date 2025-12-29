from django.test import TestCase
from django.core.cache import cache
from django.conf import settings
from rest_framework.test import APIClient

from accounts.models import User, OTPVerification, ShippingAddress


class AccountsFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        # Relax OTP throttling for isolated tests
        settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["otp"] = "1000/minute"

    def test_registration_creates_inactive_user_and_blocks_duplicates(self):
        payload = {"phone": "07701234567", "password": "secret123"}
        res = self.client.post("/api/accounts/register", payload, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["success"])

        user = User.objects.get(phone=payload["phone"])
        self.assertFalse(user.is_active)

        dup_res = self.client.post("/api/accounts/register", payload, format="json")
        self.assertEqual(dup_res.status_code, 400)
        self.assertIn("phone", dup_res.data)

    def test_verify_otp_activates_user_and_rejects_bad_code(self):
        user = User.objects.create_user(phone="07701234568", password="secret123")
        otp = OTPVerification.create_otp(user, purpose="activation")

        bad_res = self.client.post(
            "/api/accounts/verify-otp",
            {"phone": user.phone, "otp": "000000"},
            format="json",
        )
        self.assertEqual(bad_res.status_code, 400)

        res = self.client.post(
            "/api/accounts/verify-otp",
            {"phone": user.phone, "otp": otp.otp_code},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_login_respects_activation_state(self):
        inactive = User.objects.create_user(phone="07701234569", password="secret123")
        active = User.objects.create_user(phone="07701234570", password="secret123")
        active.is_active = True
        active.save()

        bad_res = self.client.post(
            "/api/accounts/login",
            {"phone": inactive.phone, "password": "secret123"},
            format="json",
        )
        self.assertEqual(bad_res.status_code, 400)

        res = self.client.post(
            "/api/accounts/login",
            {"phone": active.phone, "password": "secret123"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_password_reset_flow(self):
        user = User.objects.create_user(phone="07701234571", password="oldpass123")
        user.is_active = True
        user.save()

        res = self.client.post(
            "/api/accounts/request-reset", {"phone": user.phone}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        otp = OTPVerification.objects.filter(
            user=user, purpose="password_reset"
        ).latest("created_at")

        reset_res = self.client.post(
            "/api/accounts/reset-password",
            {"phone": user.phone, "otp": otp.otp_code, "new_password": "newpass456"},
            format="json",
        )
        self.assertEqual(reset_res.status_code, 200)

        login_res = self.client.post(
            "/api/accounts/login",
            {"phone": user.phone, "password": "newpass456"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

    def test_shipping_address_uses_authenticated_user(self):
        user = User.objects.create_user(phone="07701234572", password="secret123")
        user.is_active = True
        user.save()
        self.client.force_authenticate(user=user)

        res = self.client.get("/api/accounts/me/profile/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["user"]["id"], user.id)

        patch_res = self.client.patch(
            "/api/accounts/me/profile/",
            {"city": "Baghdad", "city_id": 1, "region": "Karrada", "region_id": 2},
            format="json",
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["user"]["id"], user.id)

        address = ShippingAddress.objects.get(user=user)
        self.assertEqual(address.city, "Baghdad")
        self.assertEqual(address.region, "Karrada")
