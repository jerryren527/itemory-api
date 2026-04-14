from django.test import TestCase
from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core import mail
import re
from rest_framework_simplejwt.tokens import RefreshToken


# get_user_model will return whatever model is set in settings.AUTH_USER_MODEL
User = get_user_model()

# Create your tests here.


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
