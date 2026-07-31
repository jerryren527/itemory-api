from django.test import TestCase
from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core import mail
import re
from unittest.mock import patch
from rest_framework_simplejwt.tokens import RefreshToken
from app.models import Home, HomeMembership, Room, Container, Item


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
        User.objects.create_user(email=GOOGLE_EMAIL, google_sub=GOOGLE_SUB,
                                 google_account_linked=True, email_verified=True)
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
        # Cleared authentication header. DRF returns 401 before even calling view function.
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
            "username": "testuser",
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
        url = reverse("app:register")
        response = self.client.post(
            url, {"email": "testuserexample.com", "password": "StrongPassword123!"},
            format="json")
        self.assertEqual(response.status_code, 400)

    def test_missing_email_returns_400(self):
        url = reverse("app:register")
        response = self.client.post(url, {"password": "StrongPassword123!"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_missing_password_returns_400(self):
        url = reverse("app:register")
        response = self.client.post(url, {"email": "testuser@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_weak_password_no_uppercase_returns_400(self):
        url = reverse("app:register")
        response = self.client.post(url, {"email": "testuser@example.com", "password": "password123!"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_weak_password_no_number_returns_400(self):
        url = reverse("app:register")
        response = self.client.post(url, {"email": "testuser@example.com", "password": "Password!"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_weak_password_no_special_char_returns_400(self):
        url = reverse("app:register")
        response = self.client.post(url, {"email": "testuser@example.com", "password": "Password123"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_email_stored_lowercase(self):
        url = reverse("app:register")
        self.client.post(
            url, {"email": "TestUser@Example.COM", "password": "StrongPassword123!", "username": "testuser"},
            format="json")
        user = User.objects.first()
        self.assertEqual(user.email, "testuser@example.com")

    def test_has_password_set_after_registration(self):
        url = reverse("app:register")
        self.client.post(
            url, {"email": "testuser@example.com", "password": "StrongPassword123!", "username": "testuser"},
            format="json")
        user = User.objects.first()
        self.assertTrue(user.has_password)

    def test_email_not_verified_before_clicking_link(self):
        url = reverse("app:register")
        self.client.post(
            url, {"email": "testuser@example.com", "password": "StrongPassword123!", "username": "testuser"},
            format="json")
        user = User.objects.first()
        self.assertFalse(user.email_verified)


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
        self.url = reverse("app:login")
        self.user = User.objects.create_user(
            email="testuser@example.com",
            username="testuser",
            password="StrongPassword123!",
            email_verified=True,
        )

    def _post(self, identifier="testuser@example.com", password="StrongPassword123!"):
        return self.client.post(self.url, {"identifier": identifier, "password": password}, format="json")

    def test_successful_login_returns_200(self):
        self.assertEqual(self._post().status_code, 200)

    def test_successful_login_response_shape(self):
        response = self._post()
        for key in ("id", "email", "tokens", "has_password", "email_verified", "google_account_linked", "primary_home"):
            self.assertIn(key, response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_wrong_password_returns_401(self):
        self.assertEqual(self._post(password="WrongPassword1!").status_code, 401)

    def test_nonexistent_email_returns_401(self):
        self.assertEqual(self._post(identifier="nobody@example.com").status_code, 401)

    def test_unverified_user_cannot_login(self):
        User.objects.create_user(
            email="unverified@example.com",
            password="StrongPassword123!",
            email_verified=False,
        )
        self.assertEqual(self._post(identifier="unverified@example.com").status_code, 401)

    def test_email_login_is_case_insensitive(self):
        self.assertEqual(self._post(identifier="TESTUSER@EXAMPLE.COM").status_code, 200)

    def test_username_login_returns_200(self):
        self.assertEqual(self._post(identifier="testuser").status_code, 200)

    def test_username_login_is_case_insensitive(self):
        self.assertEqual(self._post(identifier="TestUser").status_code, 200)

    def test_nonexistent_username_returns_401(self):
        self.assertEqual(self._post(identifier="nobodyuser").status_code, 401)

    def test_missing_identifier_returns_401(self):
        response = self.client.post(self.url, {"password": "StrongPassword123!"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_missing_password_returns_401(self):
        response = self.client.post(self.url, {"identifier": "testuser@example.com"}, format="json")
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


class SearchNodesTests(APITestCase):

    def setUp(self):
        self.url = reverse("app:search-nodes")

        self.user = User.objects.create_user(
            email="searcher@example.com",
            password="Pass123!",
            email_verified=True,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Pass123!",
            email_verified=True,
        )

        # Home the searching user belongs to.
        self.home = Home.objects.create(name="My Home", created_by=self.user)
        HomeMembership.objects.create(user=self.user, home=self.home)

        self.room = Room.objects.create(name="Kitchen", home=self.home, created_by=self.user)
        self.other_room = Room.objects.create(name="Garage", home=self.home, created_by=self.user)

        self.container = Container.objects.create(
            name="Kitchen Cabinet", room=self.room, level=1, created_by=self.user,
        )
        self.nested_container = Container.objects.create(
            name="Top Shelf", parent_container=self.container, level=2, created_by=self.user,
        )

        self.room_item = Item.objects.create(name="Kitchen Knife", room=self.room, created_by=self.user)
        self.container_item = Item.objects.create(name="Blender", container=self.container, created_by=self.user)
        self.nested_item = Item.objects.create(
            name="Spice Rack Kitchen", container=self.nested_container, created_by=self.user,
        )

        # A home the searching user does NOT belong to — must never appear in results.
        self.foreign_home = Home.objects.create(name="Other Home", created_by=self.other_user)
        HomeMembership.objects.create(user=self.other_user, home=self.foreign_home)
        self.foreign_room = Room.objects.create(
            name="Kitchen Foreign", home=self.foreign_home, created_by=self.other_user,
        )

    def _get(self, params):
        return self.client.get(self.url, params)

    # --- Validation ---

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self._get({"q": "kitchen", "scope": "everywhere"})
        self.assertEqual(response.status_code, 401)

    def test_missing_q_returns_400(self):
        response = self._get({"scope": "everywhere"})
        self.assertEqual(response.status_code, 400)

    def test_blank_q_returns_400(self):
        response = self._get({"q": "   ", "scope": "everywhere"})
        self.assertEqual(response.status_code, 400)

    def test_missing_scope_returns_400(self):
        response = self._get({"q": "kitchen"})
        self.assertEqual(response.status_code, 400)

    def test_invalid_scope_returns_400(self):
        response = self._get({"q": "kitchen", "scope": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_folder_scope_missing_origin_type_returns_400(self):
        response = self._get({"q": "kitchen", "scope": "folder", "origin_id": self.home.id})
        self.assertEqual(response.status_code, 400)

    def test_folder_scope_missing_origin_id_returns_400(self):
        response = self._get({"q": "kitchen", "scope": "folder", "origin_type": "home"})
        self.assertEqual(response.status_code, 400)

    def test_folder_scope_non_integer_origin_id_returns_400(self):
        response = self._get({
            "q": "kitchen", "scope": "folder", "origin_type": "home", "origin_id": "abc",
        })
        self.assertEqual(response.status_code, 400)

    def test_folder_scope_home_not_accessible_returns_404(self):
        response = self._get({
            "q": "kitchen", "scope": "folder", "origin_type": "home", "origin_id": self.foreign_home.id,
        })
        self.assertEqual(response.status_code, 404)

    def test_folder_scope_nonexistent_room_returns_404(self):
        response = self._get({
            "q": "kitchen", "scope": "folder", "origin_type": "room", "origin_id": 999999,
        })
        self.assertEqual(response.status_code, 404)

    # --- everywhere scope ---

    def test_everywhere_scope_matches_room_container_and_items(self):
        response = self._get({"q": "kitchen", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertEqual(
            names,
            {"Kitchen", "Kitchen Cabinet", "Kitchen Knife", "Spice Rack Kitchen"},
        )

    def test_everywhere_scope_is_case_insensitive(self):
        response = self._get({"q": "KITCHEN", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertIn("Kitchen", names)

    def test_everywhere_scope_excludes_other_users_homes(self):
        response = self._get({"q": "kitchen", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertNotIn("Kitchen Foreign", names)

    def test_everywhere_scope_no_match_returns_empty_results(self):
        response = self._get({"q": "nonexistentitem", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_response_shape_includes_query_scope_and_home_tags(self):
        response = self._get({"q": "kitchen", "scope": "everywhere"})
        self.assertEqual(response.data["query"], "kitchen")
        self.assertEqual(response.data["scope"], "everywhere")
        for result in response.data["results"]:
            self.assertEqual(result["home_id"], self.home.id)
            self.assertEqual(result["home_name"], self.home.name)
            self.assertIn("type", result)
            self.assertIn("id", result)

    # --- folder scope: home ---

    def test_folder_scope_home_returns_matches_within_home(self):
        response = self._get({
            "q": "kitchen", "scope": "folder", "origin_type": "home", "origin_id": self.home.id,
        })
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertEqual(
            names,
            {"Kitchen", "Kitchen Cabinet", "Kitchen Knife", "Spice Rack Kitchen"},
        )

    # --- folder scope: room ---

    def test_folder_scope_room_excludes_room_itself_and_sibling_room(self):
        response = self._get({
            "q": "kitchen", "scope": "folder", "origin_type": "room", "origin_id": self.room.id,
        })
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        # The room node itself is never a match candidate in room scope, only its descendants.
        self.assertEqual(names, {"Kitchen Cabinet", "Kitchen Knife", "Spice Rack Kitchen"})

    def test_folder_scope_room_does_not_include_other_rooms_items(self):
        Item.objects.create(name="Kitchen Mat", room=self.other_room, created_by=self.user)
        response = self._get({
            "q": "kitchen", "scope": "folder", "origin_type": "room", "origin_id": self.room.id,
        })
        names = {r["name"] for r in response.data["results"]}
        self.assertNotIn("Kitchen Mat", names)

    # --- folder scope: container ---

    def test_folder_scope_container_returns_only_nested_descendants(self):
        response = self._get({
            "q": "kitchen", "scope": "folder", "origin_type": "container", "origin_id": self.container.id,
        })
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        # Only descendants of `container` match; the container itself and the
        # room-level item are excluded.
        self.assertEqual(names, {"Spice Rack Kitchen"})

    def test_folder_scope_container_not_accessible_returns_404(self):
        foreign_container = Container.objects.create(
            name="Foreign Cabinet", room=self.foreign_room, level=1, created_by=self.other_user,
        )
        response = self._get({
            "q": "kitchen", "scope": "folder", "origin_type": "container", "origin_id": foreign_container.id,
        })
        self.assertEqual(response.status_code, 404)

    # --- item matching on category and tags ---

    def test_everywhere_scope_matches_item_by_category(self):
        Item.objects.create(
            name="Toaster", room=self.room, created_by=self.user, category="kitchen",
        )
        response = self._get({"q": "kitchen", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertIn("Toaster", names)

    def test_everywhere_scope_matches_item_by_tag(self):
        Item.objects.create(
            name="Widget", room=self.other_room, created_by=self.user, tags=["outdoor", "camping"],
        )
        response = self._get({"q": "camping", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertEqual(names, {"Widget"})

    def test_everywhere_scope_tag_match_is_case_insensitive_and_partial(self):
        Item.objects.create(
            name="Widget", room=self.other_room, created_by=self.user, tags=["Camping"],
        )
        response = self._get({"q": "CAMP", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertEqual(names, {"Widget"})

    def test_everywhere_scope_no_tag_match_returns_empty(self):
        Item.objects.create(
            name="Widget", room=self.other_room, created_by=self.user, tags=["outdoor"],
        )
        response = self._get({"q": "nonexistenttag", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_everywhere_scope_item_with_null_tags_does_not_error(self):
        Item.objects.create(name="Widget", room=self.other_room, created_by=self.user)
        response = self._get({"q": "widget", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertEqual(names, {"Widget"})

    def test_everywhere_scope_tag_match_excludes_other_users_items(self):
        Item.objects.create(
            name="Foreign Widget", room=self.foreign_room, created_by=self.other_user, tags=["camping"],
        )
        response = self._get({"q": "camping", "scope": "everywhere"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertNotIn("Foreign Widget", names)


class ItemUniqueNameTests(APITestCase):
    """
    Item names must be unique among siblings in the same room/container, but
    the same name is allowed to repeat in a different room/container.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="itemowner@example.com",
            password="Pass123!",
            email_verified=True,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        self.home = Home.objects.create(name="My Home", created_by=self.user)
        HomeMembership.objects.create(user=self.user, home=self.home)

        self.room = Room.objects.create(name="Kitchen", home=self.home, created_by=self.user)
        self.other_room = Room.objects.create(name="Garage", home=self.home, created_by=self.user)
        self.container = Container.objects.create(
            name="Cabinet", room=self.room, level=1, created_by=self.user,
        )

        self.room_item = Item.objects.create(name="Blender", room=self.room, created_by=self.user)
        self.container_item = Item.objects.create(name="Mug", container=self.container, created_by=self.user)

    # --- create_item ---

    def test_create_item_duplicate_name_in_same_room_returns_400(self):
        response = self.client.post(
            reverse("app:create-item"), {"name": "Blender", "room_id": self.room.id}, format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Item.objects.filter(room=self.room, name="Blender").count() > 1)

    def test_create_item_duplicate_name_in_same_container_returns_400(self):
        response = self.client.post(
            reverse("app:create-item"), {"name": "Mug", "container_id": self.container.id}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_item_same_name_in_different_room_is_allowed(self):
        response = self.client.post(
            reverse("app:create-item"), {"name": "Blender", "room_id": self.other_room.id}, format="json",
        )
        self.assertEqual(response.status_code, 201)

    # --- rename_node ---

    def test_rename_item_to_duplicate_name_in_same_room_returns_400(self):
        other_item = Item.objects.create(name="Toaster", room=self.room, created_by=self.user)
        response = self.client.post(
            reverse("app:rename-node", args=["item", other_item.id]), {"name": "Blender"}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rename_item_to_its_own_current_name_is_allowed(self):
        response = self.client.post(
            reverse("app:rename-node", args=["item", self.room_item.id]), {"name": "Blender"}, format="json",
        )
        self.assertEqual(response.status_code, 200)

    # --- update_item ---

    def test_update_item_name_to_duplicate_in_same_container_returns_400(self):
        other_item = Item.objects.create(name="Plate", container=self.container, created_by=self.user)
        response = self.client.post(
            reverse("app:update-item", args=[other_item.id]), {"name": "Mug"}, format="json",
        )
        self.assertEqual(response.status_code, 400)


class OptimisticConcurrencyTests(APITestCase):
    """
    expected_updated_at is optional (old clients omit it and skip the check
    entirely) but, when present, must be atomically compared against the
    row's real updated_at before any write is applied.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="occowner@example.com",
            password="Pass123!",
            email_verified=True,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        self.home = Home.objects.create(name="My Home", created_by=self.user)
        HomeMembership.objects.create(user=self.user, home=self.home)
        self.room = Room.objects.create(name="Kitchen", home=self.home, created_by=self.user)
        self.item = Item.objects.create(name="Blender", room=self.room, created_by=self.user)

    def _iso(self, dt):
        return dt.isoformat()

    # --- rename_home ---

    def test_rename_home_without_expected_updated_at_succeeds(self):
        response = self.client.post(
            reverse("app:rename-home", args=[self.home.id]), {"name": "New Name"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.home.refresh_from_db()
        self.assertEqual(self.home.name, "New Name")

    def test_rename_home_with_matching_expected_updated_at_succeeds(self):
        response = self.client.post(
            reverse("app:rename-home", args=[self.home.id]),
            {"name": "New Name", "expected_updated_at": self._iso(self.home.updated_at)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("updated_at", response.data)

    def test_rename_home_with_stale_expected_updated_at_returns_409_and_does_not_write(self):
        stale = self._iso(self.home.updated_at)
        self.home.name = "Changed By Someone Else"
        self.home.save()

        response = self.client.post(
            reverse("app:rename-home", args=[self.home.id]),
            {"name": "My Attempted Rename", "expected_updated_at": stale},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.home.refresh_from_db()
        self.assertEqual(self.home.name, "Changed By Someone Else")

    def test_rename_home_with_malformed_expected_updated_at_returns_400(self):
        response = self.client.post(
            reverse("app:rename-home", args=[self.home.id]),
            {"name": "New Name", "expected_updated_at": "not-a-date"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # --- update_home_address ---

    def test_update_home_address_with_stale_expected_updated_at_returns_409(self):
        stale = self._iso(self.home.updated_at)
        self.home.address = "123 Main St"
        self.home.save()

        response = self.client.post(
            reverse("app:update-home-address", args=[self.home.id]),
            {"address": "456 Oak Ave", "expected_updated_at": stale},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.home.refresh_from_db()
        self.assertEqual(self.home.address, "123 Main St")

    # --- rename_node ---

    def test_rename_node_with_matching_expected_updated_at_succeeds_and_returns_updated_at(self):
        response = self.client.post(
            reverse("app:rename-node", args=["room", self.room.id]),
            {"name": "Pantry", "expected_updated_at": self._iso(self.room.updated_at)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("updated_at", response.data)

    def test_rename_node_with_stale_expected_updated_at_returns_409(self):
        stale = self._iso(self.room.updated_at)
        self.room.name = "Changed By Someone Else"
        self.room.save()

        response = self.client.post(
            reverse("app:rename-node", args=["room", self.room.id]),
            {"name": "My Attempted Rename", "expected_updated_at": stale},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.room.refresh_from_db()
        self.assertEqual(self.room.name, "Changed By Someone Else")

    # --- update_item ---

    def test_update_item_with_stale_expected_updated_at_returns_409_and_does_not_write(self):
        stale = self._iso(self.item.updated_at)
        self.item.description = "Changed By Someone Else"
        self.item.save()

        response = self.client.post(
            reverse("app:update-item", args=[self.item.id]),
            {"description": "My Attempted Edit", "expected_updated_at": stale},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.item.refresh_from_db()
        self.assertEqual(self.item.description, "Changed By Someone Else")

    def test_update_item_with_matching_expected_updated_at_succeeds_and_returns_updated_at(self):
        response = self.client.post(
            reverse("app:update-item", args=[self.item.id]),
            {"description": "A blender", "expected_updated_at": self._iso(self.item.updated_at)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("updated_at", response.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.description, "A blender")
