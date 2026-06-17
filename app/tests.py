from django.test import TestCase
from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core import mail
import re
from unittest.mock import patch
from rest_framework_simplejwt.tokens import RefreshToken


# get_user_model will return whatever model is set in settings.AUTH_USER_MODEL
User = get_user_model()

# Create your tests here.


APPLE_SUB = "apple.sub.abc123"
APPLE_EMAIL = "appleuser@privaterelay.appleid.com"

VALID_APPLE_PAYLOAD = {"sub": APPLE_SUB, "email": APPLE_EMAIL}
VALID_APPLE_PAYLOAD_NO_EMAIL = {"sub": APPLE_SUB}

GOOGLE_SUB = "google.sub.xyz789"
GOOGLE_EMAIL = "googleuser@gmail.com"

VALID_GOOGLE_IDINFO = {
    "sub": GOOGLE_SUB,
    "email": GOOGLE_EMAIL,
    "email_verified": True,
    "name": "Google User",
    "picture": "https://example.com/photo.jpg",
}


class GoogleSignInTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:google-sign-in")

    def _post(self, payload=None):
        return self.client.post(self.url, payload or {"idToken": "tok"}, format="json")

    def test_missing_id_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("app.views.id_token.verify_oauth2_token", side_effect=Exception("bad token"))
    def test_invalid_token_returns_400(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 400)

    @patch("app.views.id_token.verify_oauth2_token", return_value={**VALID_GOOGLE_IDINFO, "email_verified": False})
    def test_unverified_email_returns_400(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 400)

    @patch("app.views.id_token.verify_oauth2_token", return_value=VALID_GOOGLE_IDINFO)
    def test_new_user_is_created_and_tokens_returned(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("access_token", response.data)
        user = User.objects.get(email=GOOGLE_EMAIL)
        self.assertEqual(user.google_sub, GOOGLE_SUB)
        self.assertTrue(user.google_account_linked)
        self.assertTrue(user.email_verified)

    @patch("app.views.id_token.verify_oauth2_token", return_value=VALID_GOOGLE_IDINFO)
    def test_returning_user_matched_by_sub(self, _mock):
        User.objects.create_user(email=GOOGLE_EMAIL, google_sub=GOOGLE_SUB, google_account_linked=True, email_verified=True)
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(User.objects.count(), 1)

    @patch("app.views.id_token.verify_oauth2_token", return_value=VALID_GOOGLE_IDINFO)
    def test_email_collision_with_existing_account_returns_409(self, _mock):
        User.objects.create_user(email=GOOGLE_EMAIL, password="Pass123!", has_password=True, email_verified=True)
        response = self._post()
        self.assertEqual(response.status_code, 409)


class GoogleLinkTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:google-link")
        self.user = User.objects.create_user(
            email="user@example.com",
            password="Pass123!",
            has_password=True,
            email_verified=True,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def _post(self, payload=None):
        return self.client.post(self.url, payload or {"idToken": "tok"}, format="json")

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        self.assertEqual(self._post().status_code, 401)

    def test_missing_id_token_returns_400(self):
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 400)

    @patch("app.views.id_token.verify_oauth2_token", return_value=VALID_GOOGLE_IDINFO)
    def test_link_sets_google_sub_on_current_user(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.google_sub, GOOGLE_SUB)
        self.assertTrue(self.user.google_account_linked)

    @patch("app.views.id_token.verify_oauth2_token", return_value=VALID_GOOGLE_IDINFO)
    def test_already_linked_to_current_user_is_noop(self, _mock):
        self.user.google_sub = GOOGLE_SUB
        self.user.google_account_linked = True
        self.user.save()
        self.assertEqual(self._post().status_code, 200)

    @patch("app.views.id_token.verify_oauth2_token", return_value=VALID_GOOGLE_IDINFO)
    def test_empty_other_user_is_deleted_and_sub_transferred(self, _mock):
        empty_user = User.objects.create_user(
            email="ghost@example.com",
            google_sub=GOOGLE_SUB,
            google_account_linked=True,
        )
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=empty_user.pk).exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.google_sub, GOOGLE_SUB)

    @patch("app.views.id_token.verify_oauth2_token", return_value=VALID_GOOGLE_IDINFO)
    def test_other_user_with_data_returns_409(self, _mock):
        from app.models import Home, HomeMembership
        other_user = User.objects.create_user(
            email="other@example.com",
            google_sub=GOOGLE_SUB,
            google_account_linked=True,
        )
        home = Home.objects.create(name="Test Home", created_by=other_user)
        HomeMembership.objects.create(user=other_user, home=home)
        self.assertEqual(self._post().status_code, 409)


class GoogleUnlinkTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:google-unlink")
        self.user = User.objects.create_user(
            email="user@example.com",
            google_sub=GOOGLE_SUB,
            google_account_linked=True,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def _post(self):
        return self.client.post(self.url, format="json")

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        self.assertEqual(self._post().status_code, 401)

    def test_not_linked_returns_400(self):
        self.user.google_sub = None
        self.user.google_account_linked = False
        self.user.save()
        self.assertEqual(self._post().status_code, 400)

    def test_only_login_method_blocked(self):
        self.assertEqual(self._post().status_code, 400)

    def test_unlink_succeeds_when_password_exists(self):
        self.user.has_password = True
        self.user.set_password("Pass123!")
        self.user.save()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.google_sub)
        self.assertFalse(self.user.google_account_linked)
        self.assertIsNone(self.user.google_picture_url)

    def test_unlink_succeeds_when_apple_linked(self):
        self.user.apple_sub = APPLE_SUB
        self.user.save()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.google_sub)


class AppleSignInTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:apple-sign-in")

    def _post(self, payload=None):
        return self.client.post(self.url, payload or {"identityToken": "tok"}, format="json")

    def test_missing_identity_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("app.views._verify_apple_identity_token", side_effect=Exception("bad sig"))
    def test_invalid_token_returns_400(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 400)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_unknown_sub_returns_new_apple_user(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "new_apple_user")
        self.assertEqual(User.objects.count(), 0)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_known_sub_returns_tokens(self, _mock):
        User.objects.create_user(email=APPLE_EMAIL, apple_sub=APPLE_SUB, apple_account_linked=True)
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)


class AppleConfirmTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:apple-confirm")

    def _post(self, payload=None):
        return self.client.post(self.url, payload or {"identityToken": "tok"}, format="json")

    def test_missing_identity_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD_NO_EMAIL)
    def test_no_email_in_payload_returns_400(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 400)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_new_user_is_created_and_tokens_returned(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("access_token", response.data)
        user = User.objects.get(email=APPLE_EMAIL)
        self.assertEqual(user.apple_sub, APPLE_SUB)
        self.assertTrue(user.apple_account_linked)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_already_registered_sub_returns_tokens_without_duplicate(self, _mock):
        User.objects.create_user(email=APPLE_EMAIL, apple_sub=APPLE_SUB, apple_account_linked=True)
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(User.objects.count(), 1)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_email_already_exists_returns_409(self, _mock):
        User.objects.create_user(email=APPLE_EMAIL, password="Pass123!", has_password=True)
        response = self._post()
        self.assertEqual(response.status_code, 409)


class AppleLinkTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:apple-link")
        self.user = User.objects.create_user(
            email="user@example.com",
            password="Pass123!",
            has_password=True,
            email_verified=True,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def _post(self, payload=None):
        return self.client.post(self.url, payload or {"identityToken": "tok"}, format="json")

    def test_unauthenticated_returns_401(self):
        # clears the token, no longer authenticated. DRF returns 401 before even calling view function.
        self.client.credentials()
        response = self._post()
        self.assertEqual(response.status_code, 401)

    def test_missing_identity_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_link_sets_apple_sub_on_current_user(self, _mock):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_sub, APPLE_SUB)
        self.assertTrue(self.user.apple_account_linked)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_already_linked_to_current_user_is_noop(self, _mock):
        self.user.apple_sub = APPLE_SUB
        self.user.apple_account_linked = True
        self.user.save()
        response = self._post()
        self.assertEqual(response.status_code, 200)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_empty_other_user_is_deleted_and_sub_transferred(self, _mock):
        from app.models import HomeMembership
        empty_user = User.objects.create_user(
            email="ghost@example.com",
            apple_sub=APPLE_SUB,
            apple_account_linked=True,
        )
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=empty_user.pk).exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_sub, APPLE_SUB)

    @patch("app.views._verify_apple_identity_token", return_value=VALID_APPLE_PAYLOAD)
    def test_other_user_with_data_returns_409(self, _mock):
        from app.models import Home, HomeMembership
        other_user = User.objects.create_user(
            email="other@example.com",
            apple_sub=APPLE_SUB,
            apple_account_linked=True,
        )
        home = Home.objects.create(name="Test Home", created_by=other_user)
        HomeMembership.objects.create(user=other_user, home=home)
        response = self._post()
        self.assertEqual(response.status_code, 409)


class AppleUnlinkTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:apple-unlink")
        self.user = User.objects.create_user(
            email="user@example.com",
            apple_sub=APPLE_SUB,
            apple_account_linked=True,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def _post(self):
        return self.client.post(self.url, format="json")

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        self.assertEqual(self._post().status_code, 401)

    def test_not_linked_returns_400(self):
        self.user.apple_sub = None
        self.user.apple_account_linked = False
        self.user.save()
        self.assertEqual(self._post().status_code, 400)

    def test_only_login_method_blocked(self):
        # user has no password and no google_sub
        response = self._post()
        self.assertEqual(response.status_code, 400)

    def test_unlink_succeeds_when_password_exists(self):
        self.user.has_password = True
        self.user.set_password("Pass123!")
        self.user.save()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.apple_sub)
        self.assertFalse(self.user.apple_account_linked)

    def test_unlink_succeeds_when_google_linked(self):
        self.user.google_sub = "google.sub.xyz"
        self.user.save()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.apple_sub)


class RegisterTests(APITestCase):

    def test_user_is_verified_after_clicking_email_verification_link(self):
        """
        Test that email verification is sent after user registers. And that user.email_verified is True after clicking on the email verification link.
        """
        url = reverse("app:register")  # app/register

        data = {
            "email": "testuser@example.com",
            "password": "StrongPassword123!",
        }

        response = self.client.post(url, data, format="json")

        # User was created
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertEqual(user.email, "testuser@example.com")

        # One email was sent
        self.assertEqual(len(mail.outbox), 1)

        # print(f"mail.outbox: {mail.outbox}")
        email = mail.outbox[0]

        # Extract link
        match = re.search(r"http://[^/]+(.+)", email.body)
        # print(f"match: {match}")
        self.assertIsNotNone(match)

        verification_path = match.group(1)
        # print(f"verification_path: {verification_path}")

        # print(f"email.subject: {email.subject}")
        # print(f"email.to: {email.to}")
        # print(f"email.body: {email.body}")

        # Email content checks
        self.assertIn("Verify your email address", email.subject)
        self.assertIn("testuser@example.com", email.to)
        self.assertIn("Click here to verify", email.body)
        # verification emails typically contain a link like "http://..."
        self.assertIn("http", email.body)

        self.assertEqual(response.status_code, 200)

        # Simulate clicking on link
        verify_response = self.client.get(verification_path)
        # print(f"verify_response: {verify_response}")

        # Assert verified
        user = User.objects.get(email='testuser@example.com')
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    def test_register_with_invalid_email_returns_400(self):
        """
        Test that registering an invalid email returns 400 error.
        """
        # Register a user
        url = reverse("app:register")  # app/register

        data = {
            "email": "testuserexample.com",  # invalid email format
            "password": "StrongPassword123!",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)


class RegisterConflictTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:register")
        self.data = {"email": "user@example.com", "password": "StrongPassword123!"}

    def _post(self):
        return self.client.post(self.url, self.data, format="json")

    def test_google_only_user_returns_409_with_google_flag(self):
        User.objects.create_user(
            email="user@example.com",
            google_sub=GOOGLE_SUB,
            google_account_linked=True,
            email_verified=True,
        )
        response = self._post()
        self.assertEqual(response.status_code, 409)
        self.assertIn("Google", response.data["message"])
        self.assertTrue(response.data["user_has_google"])
        self.assertFalse(response.data["user_has_apple"])

    def test_apple_only_user_returns_409_with_apple_flag(self):
        User.objects.create_user(
            email="user@example.com",
            apple_sub=APPLE_SUB,
            apple_account_linked=True,
            email_verified=True,
        )
        response = self._post()
        self.assertEqual(response.status_code, 409)
        self.assertIn("Apple", response.data["message"])
        self.assertFalse(response.data["user_has_google"])
        self.assertTrue(response.data["user_has_apple"])

    def test_google_and_apple_user_returns_409_with_both_flags(self):
        User.objects.create_user(
            email="user@example.com",
            google_sub=GOOGLE_SUB,
            google_account_linked=True,
            apple_sub=APPLE_SUB,
            apple_account_linked=True,
            email_verified=True,
        )
        response = self._post()
        self.assertEqual(response.status_code, 409)
        self.assertIn("Google", response.data["message"])
        self.assertIn("Apple", response.data["message"])
        self.assertTrue(response.data["user_has_google"])
        self.assertTrue(response.data["user_has_apple"])

    def test_unverified_email_password_user_resends_verification_email(self):
        User.objects.create_user(
            email="user@example.com",
            password="StrongPassword123!",
            has_password=True,
            email_verified=False,
        )
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_verified_email_password_user_returns_409(self):
        User.objects.create_user(
            email="user@example.com",
            password="StrongPassword123!",
            has_password=True,
            email_verified=True,
        )
        response = self._post()
        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.data["message"])


class LoginTests(APITestCase):

    def setUp(self):
        """
        Runs before every testcase. Creates test user in database.
        """
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="StrongPassword123!",
            email_verified=True
        )

    def test_successful_login(self):
        """
        Test successful login of user who has verified their email address.
        """
        url = reverse("app:login")  # app/login

        data = {
            "email": "testuser@example.com",
            "password": "StrongPassword123!",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)

    def test_failure_login(self):
        """
        Test failure login of a user that is not in the databse.
        """
        url = reverse("app:login")  # app/login

        data = {
            "email": "testuser2@example.com",
            "password": "StrongPassword123!",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 401)


class ProtectedTests(APITestCase):

    def setUp(self):
        """
        Create user and the SimpleJWT.
        """
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="StrongPassword123!",
        )

        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        self.url = reverse("app:test-view")

    def test_unauthenticated_user_returns_401(self):
        """
        Test that unauthenticated users are rejected.
        """
        response = self.client.get(self.url)

        self.assertTrue(response.status_code, 401)

    def test_authenticated_user_returns_200(self):
        """
        Test that authenticated users are accepted.
        """
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.get(self.url)

        # print(f"response.data: {response.data}")

        self.assertEqual(response.status_code, 200)
