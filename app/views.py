from rest_framework import permissions, viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.csrf import csrf_exempt
import requests
import os
from dotenv import load_dotenv
import json
from urllib.parse import quote  # escape invalid characters in url string
from django.http import HttpResponseRedirect
from google.oauth2 import id_token
from google.auth.transport import requests as google_auth_requests
import jwt as pyjwt
from rest_framework_simplejwt.tokens import RefreshToken
from django.core import signing
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.shortcuts import render
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework import serializers, permissions
from django.core.mail import send_mail
from django.core.signing import TimestampSigner
from datetime import timedelta, datetime
from django.contrib.auth import authenticate
from django.db.models import Q, BooleanField
from django.db.models.expressions import RawSQL
import time
# from .services import place_node_helpers
from .services.search_helpers import (
    resolve_search_scope,
    resolve_container_home,
    get_container_ids_for_home,
    get_container_ids_under_room,
    get_container_subtree_ids,
    get_home_id_for_item,
    get_home_ids_for_user,
)
from .services.username_helpers import generate_unique_username
from .services.photo_helpers import ALLOWED_PHOTO_CONTENT_TYPES, delete_item_photo, presign_item_photo_upload

from .models import CustomUser, PasswordResetToken, Room, Container, Item, ItemCheckout, Home, HomeMembership, StarredRoom, StarredContainer, StarredItem
from .serializers import RegisterSerializer, IdentifySerializer, LoginSerializer, ResetPasswordSerializer, SetPasswordSerializer, ChildSerializer, NodeDetailsSerializer, ItemNodeDetailsSerializer, HomeSerializer, SearchResultSerializer, CheckedOutItemSerializer, StarredNodeSerializer
from django.core.exceptions import ObjectDoesNotExist


# Load environment variables from .env file
load_dotenv()


@api_view(['GET'])
def me(request):
    """
    Return the authenticated user's email address.
    """
    # When you use DRF and SimpleJWT, the authentication middleware already decodes the token and provides a useful reqeuest object.
    # Get the user from the request object.
    user = request.user
    # user.email
    # user.email_verified
    # user.has_password
    # user.google_account_linked
    # user.google_sub
    # user.id
    user_json = {
        "email": user.email,
        "username": user.username,
        "email_verified": user.email_verified,
        "has_password": user.has_password,
        "google_account_linked": user.google_account_linked,
        "google_sub": user.google_sub,
        "google_email": user.google_email,
        "apple_account_linked": user.apple_account_linked,
        "id": user.id,
        "primary_home": user.primary_home.id if user.primary_home else None,
    }

    return Response(user_json, status=status.HTTP_200_OK)


@api_view(['GET'])
def test_view(request):
    # raise AuthenticationFailed("test")  # returns 401
    # print('===INSIDE TEST_VIEW===')

    # print('request.user:', request.user)
    # print('request.auth:', request.auth)

    res = {
        "message": "Inside Test View"
    }
    return Response(res, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login(request):
    try:
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            identifier = serializer.validated_data['identifier'].strip().lower()
            password = serializer.validated_data['password']

            matched_user = CustomUser.objects.filter(
                Q(email__iexact=identifier) | Q(username__iexact=identifier)
            ).first()

            user = authenticate(email=matched_user.email, password=password) if matched_user else None

            if user and user.email_verified:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    },
                    'has_password': user.has_password,
                    'email_verified': user.email_verified,
                    'google_account_linked': user.google_account_linked,
                    'google_email': user.google_email,
                    'apple_account_linked': user.apple_account_linked,
                    'primary_home': user.primary_home.id if user.primary_home else None,
                }, status=status.HTTP_200_OK)
            elif user:
                return Response({'message': 'Email address is not verified yet.'}, status=status.HTTP_401_UNAUTHORIZED)
            else:
                return Response({'message': 'Email/username or password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)

        else:
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as err:
        return Response({'message': str(err)}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def verify_email(request):
    # print('===INSIDE verify_email()===')
    # Get email signing token from query params
    token = request.query_params.get("token")

    if not token:
        return Response({"detail": "Token missing."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        data = signing.loads(token, max_age=60 * 60 * 24)  # 24 hours
    except signing.SignatureExpired:
        context = {
            'error_message': 'This email verification link has expired. Please request a new verification email and try again.'
        }

        return render(request, 'verify_email_error.html', context=context, status=status.HTTP_400_BAD_REQUEST)
    except signing.BadSignature:
        context = {
            'error_message': 'This email verification link is invalid. Please request a new verification email and try again.'
        }
        return render(request, 'verify_email_error.html', context=context, status=status.HTTP_400_BAD_REQUEST)

    user_id = data["user_id"]

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    if user.email_verified:
        # print('User is already verified.')
        context = {
            'error_message': 'User is already verified.'
        }
        return render(request, 'verify_email_error.html', context=context, status=status.HTTP_400_BAD_REQUEST)
    else:
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save()
        return render(request, 'verify_email.html')


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request):
    """
    Register a email/password user.

    :param request: Description
    """

    try:
        # request.data contains the parsed request payload (typically json).
        # When you instantiate a serializer in write mode (create/update/authenticate), you must pass the incoming data using the data keyword argument. Without 'data=', the serializer will only be in read-mode -- is_valid() would raise an error, and validated_data would not exist.
        # request.data is the request payload that is sent with an HTTP request.
        register_serializer = RegisterSerializer(data=request.data)
        identify_serializer = IdentifySerializer(data=request.data)

        # Check if there is already a user with that email address in the database.
        # print('request.data["email"]:', request.data['email'])
        user = identify_serializer.get_user_by_email(
            email=request.data['email'])

        if not user:
            # Create the new user, adding it to the database.

            # Verify that the email has a valid format. serializer.is_valid() returns boolean.
            if register_serializer.is_valid():
                new_user = register_serializer.save()
                # print('new_user:', new_user)

                # print('calling RegisterSerializer.send_verification_email()...')
                # serializer.send_verification_email(user)
                register_serializer.send_verification_email(new_user)

                # send_verification_email() does not throw an error
                res = {
                    'message': 'Verification Email sent!'
                }

                return Response(res, status=status.HTTP_200_OK)
            else:
                # print("There was a Registration Error.")
                # DRF already serializes serializer.errors -- it is proper JSON. No need to stringify it.
                return Response(register_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            providers = []
            if user.google_account_linked:
                providers.append('Google')
            if user.apple_account_linked:
                providers.append('Apple')

            if providers:
                provider_str = ' and '.join(providers)
                return Response({
                    'message': f'This email is already linked to {provider_str}. Please sign in with {provider_str}.',
                    'user_has_google': user.google_account_linked,
                    'user_has_apple': user.apple_account_linked,
                }, status=status.HTTP_409_CONFLICT)
            elif not user.email_verified:
                register_serializer.send_verification_email(user)
                return Response({'message': 'Verification Email sent!'}, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"message": "An account with this email address already exists."},
                    status=status.HTTP_409_CONFLICT,
                )

    except Exception as err:
        # print('err:', err)
        res = {
            'message': str(err)
        }
        return Response(res, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def check_email(request):
    print('=====Inside check_email()=====')

    email = request.data.get('email')

    print('email:', email)

    try:
        # Check that the entered email address string is formatted correctly.
        # Use this specific IdentifySerializer for email string validation checking.
        serializer = IdentifySerializer(data=request.data)
        # Throws a ValidationError if email string is not valid.
        serializer.is_valid(raise_exception=True)
        print('serializer.validated_data["email"]:',
              serializer.validated_data["email"])

        # print('str.lower(email):', str.lower(email)) # inconsistent email normalization

        # user = CustomUser.objects.get(email=str.lower(email)) # Throws an Exception if email not in Database. We don't want our logic to require throwing an error.
        # Gets the first CustomUser instance with this email. Use Django ORM's case-insensitive lookups with i prefix. 'iexact' is a case-insensitive exact match.
        # user = CustomUser.objects.filter(email__iexact=email).first()
        user = serializer.get_user_by_email(email)

        if user:
            print('user', user)
        else:
            print('user with this email is not in the database.')

        # status: 0, 1, 2
        # 0: Email exists and password is defined. So navigate to password page.
        # 1: Email exists, google_sub is defined, and password is not defined. So prompt user to sign in with Google.
        # 2: Email not in database.

        if not user:
            return Response({
                "message": f"We didn't find an account for {email}. Create one to continue.",
                "email_status": 2
            }, status=status.HTTP_200_OK)

        # User exists
        if user.has_password:
            return Response({
                "message": "Password login available.",
                "email_status": 0
            }, status=status.HTTP_200_OK)

        # User exists, google_sub is defined, and password is not defined.
        if user.google_sub and not user.has_password:
            return Response({
                "message": "Sign in with Google.",
                "email_status": 1
            }, status=status.HTTP_200_OK)
    except Exception as err:
        print(err)
        res = {
            "error": f"{err}",
        }
        return Response(res, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def email_sign_in(request):
    print('==========INSIDE EMAIL_SIGN_IN()!!==========')

    email = request.data.get('emailAddress')

    print('email:', email)

    res = {
        "message": "Message from email_sign_in()!"
    }

    return Response(res, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def google_sign_in(request):
    id_token_str = request.data.get('idToken')
    if not id_token_str:
        return Response({"message": "idToken is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        idInfo = id_token.verify_oauth2_token(
            id_token_str,
            google_auth_requests.Request(),
            os.getenv('GOOGLE_WEB_CLIENT_ID'),
        )
    except Exception as err:
        return Response({"message": f"Invalid Google token: {err}"}, status=status.HTTP_400_BAD_REQUEST)

    if not idInfo.get('email_verified'):
        return Response({"message": "Google email is not verified."}, status=status.HTTP_400_BAD_REQUEST)

    google_sub = idInfo['sub']

    # Returning user — look up by sub
    user = CustomUser.objects.filter(google_sub=google_sub).first()

    if not user:
        if CustomUser.objects.filter(email__iexact=idInfo['email']).exists():
            return Response(
                {"message": "An account with this email already exists. Sign in with your password and link Google from Settings."},
                status=status.HTTP_409_CONFLICT,
            )
        user = CustomUser.objects.create_user(
            email=idInfo['email'].lower(),
            google_account_linked=True,
            google_sub=google_sub,
            google_email=idInfo['email'].lower(),
            google_picture_url=idInfo.get('picture'),
            email_verified=True,
            username=generate_unique_username(idInfo.get('name') or idInfo['email'].split('@')[0]),
        )
    elif user.google_email != idInfo['email'].lower():
        user.google_email = idInfo['email'].lower()
        user.save()

    refresh = RefreshToken.for_user(user)
    return Response({
        "status": "ok",
        "name": idInfo.get('name'),
        "email": user.email,
        "username": user.username,
        "picture": idInfo.get('picture'),
        "google_sub": google_sub,
        "google_account_linked": user.google_account_linked,
        "google_email": user.google_email,
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
        "primary_home": user.primary_home.id if user.primary_home else None,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def google_link(request):
    """Link a Google account to the authenticated user."""
    id_token_str = request.data.get('idToken')
    if not id_token_str:
        return Response({"message": "idToken is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        idInfo = id_token.verify_oauth2_token(
            id_token_str,
            google_auth_requests.Request(),
            os.getenv('GOOGLE_WEB_CLIENT_ID'),
        )
    except Exception as err:
        return Response({"message": f"Invalid Google token: {err}"}, status=status.HTTP_400_BAD_REQUEST)

    if not idInfo.get('email_verified'):
        return Response({"message": "Google email is not verified."}, status=status.HTTP_400_BAD_REQUEST)

    google_sub = idInfo['sub']
    current_user = request.user

    if current_user.google_sub == google_sub:
        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    other_user = CustomUser.objects.filter(google_sub=google_sub).exclude(pk=current_user.pk).first()
    if other_user:
        other_is_empty = (
            not other_user.has_password
            and not other_user.apple_sub
            and not HomeMembership.objects.filter(user=other_user).exists()
        )
        if other_is_empty:
            other_user.delete()
        else:
            return Response(
                {"message": "This Google account is linked to another account with data. Please contact support."},
                status=status.HTTP_409_CONFLICT,
            )

    current_user.google_sub = google_sub
    current_user.google_account_linked = True
    current_user.google_email = idInfo['email'].lower()
    current_user.google_picture_url = idInfo.get('picture')
    current_user.email_verified = True
    current_user.save()
    return Response({"status": "ok", "google_email": current_user.google_email}, status=status.HTTP_200_OK)


@api_view(['POST'])
def google_unlink(request):
    """Unlink Google from the authenticated user's account."""
    user = request.user

    if not user.google_sub:
        return Response({"message": "Google account is not linked."}, status=status.HTTP_400_BAD_REQUEST)

    if not user.has_password and not user.apple_sub:
        return Response(
            {"message": "Cannot unlink Google — it is your only login method. Set a password or link another account first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.google_sub = None
    user.google_account_linked = False
    user.google_email = None
    user.google_picture_url = None
    user.save()
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


def _verify_apple_identity_token(identity_token):
    """
    Fetch Apple's public JWKS, find the matching key by kid, and verify the
    RS256-signed identity token. Returns the decoded payload on success.
    """
    response = requests.get("https://appleid.apple.com/auth/keys", timeout=10)
    apple_keys = response.json()["keys"]

    header = pyjwt.get_unverified_header(identity_token)
    matching_key = next(
        (k for k in apple_keys if k["kid"] == header.get("kid")), None
    )
    if not matching_key:
        raise ValueError("No matching Apple public key found for the provided token.")

    public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(matching_key)
    return pyjwt.decode(
        identity_token,
        key=public_key,
        algorithms=["RS256"],
        audience=os.getenv("APPLE_APP_BUNDLE_ID"),
        issuer="https://appleid.apple.com",
    )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def apple_sign_in(request):
    identity_token = request.data.get('identityToken')
    if not identity_token:
        return Response({"message": "identityToken is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = _verify_apple_identity_token(identity_token)
    except requests.exceptions.RequestException:
        return Response({"message": "Could not reach Apple's servers."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as err:
        return Response({"message": f"Invalid Apple identity token: {err}"}, status=status.HTTP_400_BAD_REQUEST)

    apple_sub = payload.get('sub')
    user = CustomUser.objects.filter(apple_sub=apple_sub).first()

    if not user:
        return Response({"status": "new_apple_user"}, status=status.HTTP_200_OK)

    refresh = RefreshToken.for_user(user)
    print("🚀 ~ views.py:476 ~ apple_sign_in ~ refresh:", refresh)
    return Response({
        "status": "ok",
        "email": user.email,
        "username": user.username,
        "apple_sub": apple_sub,
        "apple_account_linked": user.apple_account_linked,
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
        "primary_home": user.primary_home.id if user.primary_home else None,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def apple_confirm(request):
    """Create a new account for a first-time Apple user."""
    identity_token = request.data.get('identityToken')
    if not identity_token:
        return Response({"message": "identityToken is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = _verify_apple_identity_token(identity_token)
    except requests.exceptions.RequestException:
        return Response({"message": "Could not reach Apple's servers."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as err:
        return Response({"message": f"Invalid Apple identity token: {err}"}, status=status.HTTP_400_BAD_REQUEST)

    apple_sub = payload.get('sub')
    email = payload.get('email')

    if not email:
        return Response(
            {"message": "Email not provided by Apple. Please sign in with Apple again from a fresh install."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Race condition guard: sub already registered
    user = CustomUser.objects.filter(apple_sub=apple_sub).first()
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            "status": "ok",
            "email": user.email,
            "username": user.username,
            "refresh_token": str(refresh),
            "access_token": str(refresh.access_token),
            "primary_home": user.primary_home.id if user.primary_home else None,
        }, status=status.HTTP_200_OK)

    if CustomUser.objects.filter(email__iexact=email).exists():
        return Response(
            {"message": "An account with this email already exists. Log in with your password and link Apple from Settings."},
            status=status.HTTP_409_CONFLICT,
        )

    user = CustomUser.objects.create_user(
        email=email.lower(),
        apple_account_linked=True,
        apple_sub=apple_sub,
        email_verified=True,
        username=generate_unique_username(email.split('@')[0]),
    )
    refresh = RefreshToken.for_user(user)
    return Response({
        "status": "ok",
        "email": user.email,
        "username": user.username,
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
        "primary_home": user.primary_home.id if user.primary_home else None,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def apple_link(request):
    """Link an Apple account to the authenticated user.
    Used after email/password login when an existing user chooses Apple,
    and from the Settings page."""
    identity_token = request.data.get('identityToken')
    if not identity_token:
        return Response({"message": "identityToken is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = _verify_apple_identity_token(identity_token)
    except requests.exceptions.RequestException:
        return Response({"message": "Could not reach Apple's servers."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as err:
        return Response({"message": f"Invalid Apple identity token: {err}"}, status=status.HTTP_400_BAD_REQUEST)

    apple_sub = payload.get('sub')
    current_user = request.user

    if current_user.apple_sub == apple_sub:
        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    other_user = CustomUser.objects.filter(apple_sub=apple_sub).exclude(pk=current_user.pk).first()
    if other_user:
        other_is_empty = (
            not other_user.has_password
            and not other_user.google_sub
            and not HomeMembership.objects.filter(user=other_user).exists()
        )
        if other_is_empty:
            other_user.delete()
        else:
            return Response(
                {"message": "This Apple account is linked to another account with data. Please contact support."},
                status=status.HTTP_409_CONFLICT,
            )

    current_user.apple_sub = apple_sub
    current_user.apple_account_linked = True
    current_user.save()
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def apple_unlink(request):
    """Unlink Apple from the authenticated user's account."""
    user = request.user

    if not user.apple_sub:
        return Response({"message": "Apple account is not linked."}, status=status.HTTP_400_BAD_REQUEST)

    if not user.has_password and not user.google_sub:
        return Response(
            {"message": "Cannot unlink Apple — it is your only login method. Set a password or link another account first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.apple_sub = None
    user.apple_account_linked = False
    user.save()
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def set_password(request):
    """Add or change the authenticated user's password.
    Accepts an optional email for Apple relay email users who need
    to set a usable login email alongside their password."""
    user = request.user
    serializer = SetPasswordSerializer(data=request.data, context={'user': user})
    if not serializer.is_valid():
        error_message = "There was an error."
        for field in ('old_password', 'password', 'confirm_password', 'email'):
            if field in serializer.errors:
                error_message = serializer.errors[field][0]
                break
        return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)

    new_email = serializer.validated_data.get('email')
    if new_email:
        new_email = new_email.lower()
        if CustomUser.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
            return Response(
                {'message': 'An account with this email already exists.'},
                status=status.HTTP_409_CONFLICT,
            )
        user.email = new_email
        user.email_verified = False

    user.set_password(serializer.validated_data['password'])
    user.has_password = True
    user.save()

    if new_email:
        RegisterSerializer().send_verification_email(user)
        return Response({"status": "ok", "verification_email_sent": True}, status=status.HTTP_200_OK)

    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def remove_password(request):
    """Remove password login from the authenticated user's account."""
    user = request.user

    if not user.has_password:
        return Response({"message": "No password is set."}, status=status.HTTP_400_BAD_REQUEST)

    if not user.google_sub and not user.apple_sub:
        return Response(
            {"message": "Cannot remove password — it is your only login method. Link Google or Apple first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(None)
    user.has_password = False
    user.save()
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def update_username(request):
    """Change the authenticated user's username."""
    username = (request.data.get('username') or '').strip()

    if not username:
        return Response({"message": "username is required."}, status=status.HTTP_400_BAD_REQUEST)

    if CustomUser.objects.filter(username__iexact=username).exclude(pk=request.user.pk).exists():
        return Response({"message": "This username is already taken."}, status=status.HTTP_409_CONFLICT)

    user = request.user
    user.username = username
    user.save()
    return Response({"status": "ok", "username": user.username}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_reset_password_email(request):
    print('====INSIDE send_reset_password_email====')

    # Verify that the email exists in the database
    identify_serializer = IdentifySerializer(data=request.data)

    user = identify_serializer.get_user_by_email(email=request.data['email'])
    signer = TimestampSigner()

    if not user:
        res = {
            "message": 'Email DOES NOT exist!'
        }

        return Response(res, status=status.HTTP_400_BAD_REQUEST)
    else:
        res = {
            "message": 'Email exists!'
        }

        # token = signing.dumps({"user_id": user.id})
        token = signer.sign(user.id)

        # The verification url is just a normal HTTP GET link with a token passed as a query parameter. This url is emailed to the email address.
        verification_url = f"http://127.0.0.1:8000/app/reset-password/?token={token}"

        try:
            print('Adding Password Reset Token to DB...')
            record = PasswordResetToken.objects.create(
                user=user, token=token)
            print('record:', record)

            print('Sending Email...')

            send_mail(
                subject="Reset Itemory Password",
                message=f"Click here to reset your password: {verification_url}.",
                from_email="itemoryapp@gmail.com",
                recipient_list=[user.email],
                fail_silently=False,  # Will raise smtplib.SMTPException if an error occurs
            )
        except Exception as err:
            print('err:', err)

        return Response(res, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([permissions.AllowAny])
def reset_password(request):
    signer = TimestampSigner()

    token = request.query_params.get("token")

    # payload = signing.loads(token)
    # print('payload:', payload)

    if request.method == 'GET':
        print('====Inside GET reset_password()===')

        try:
            password_reset_token = PasswordResetToken.objects.get(token=token)
            print('password_reset_token:', password_reset_token)
            if password_reset_token.used_at:
                print('Password reset token as already been used.')
                context = {
                    'error_message': 'Password reset token has already been used.'
                }
                return render(request, 'reset_password_error.html', context, status=status.HTTP_401_UNAUTHORIZED)
            else:
                print('Password Reset Token has not been used yet.')
                return render(request, 'reset_password.html', status=status.HTTP_200_OK)
        except Exception as err:
            print('err:', err)
            context = {
                'error_message': err
            }
            return render(request, 'reset_password_error.html', context, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'POST':
        # TODO: complete the POST implementation

        print('====Inside POST reset_password()===')
        # token = request.query_params.get("token")
        # print('token: ', token)

        try:
            # Unsign with 15 minute expiration
            original = signer.unsign(token, max_age=timedelta(minutes=15))

            # user = CustomUser.objects.get(id=payload['user_id'])
            user = CustomUser.objects.get(id=original)
            print('user:', user)
            # Passing user into ResetPasswordSerializer() so that serializer.is_valid() can compare it to the user (auth rule: django.contrib.auth.password_validation.UserAttributeSimilarityValidator)
            serializer = ResetPasswordSerializer(data=request.data, context={
                'user': user
            })
            # serializer.is_valid(raise_exception=True)

            # Call .is_valid() to store serialized fields into self.validated_data
            if serializer.is_valid():
                password = serializer.validated_data['password']
                confirm_password = serializer.validated_data['confirm_password']

                print('password:', password)
                print('confirm_password:', confirm_password)

                # Mark the reset token record as used.
                record = PasswordResetToken.objects.get(token=token)
                print('record:', record)

                # Check if the reset password token has been used
                if record.used_at:
                    print('Reset Paswork Token already used!')
                    raise ValidationError(
                        "Reset Password link has already been used.")

                # Get the current local date and time (naive, no timezone info by default)
                current_datetime = datetime.now()
                print('Defining record.used_at to now:', current_datetime)
                record.used_at = current_datetime
                record.save()

                print('SUCCESS: Resetting password and saving user.')

                # update user password here
                user.set_password(password)
                user.save()
                return render(request, 'reset_password_success.html')
            else:
                print("error:", serializer.errors)
                print('ERROR: Unable to reset password.')

                error_message = "There was an error."

                if 'password' in serializer.errors:
                    error_message = serializer.errors['password'][0]
                elif 'confirm_password' in serializer.errors:
                    error_message = serializer.errors['confirm_password'][0]

                context = {
                    "error_message": error_message
                }
                return render(request, 'reset_password.html', context)
        except Exception as err:
            print('Error:', err)
            context = {
                "error_message": err
            }
            return render(request, 'reset_password_error.html', context, status=status.HTTP_400_BAD_REQUEST)


def determine_children(node):
    """
    Return a list of raw model instances
    """
    children = []

    if isinstance(node, Home):
        children = list(Room.objects.filter(home=node).order_by("name"))

    elif isinstance(node, Room):
        containers = Container.objects.filter(room=node).order_by("name")
        items = Item.objects.filter(room=node, container=None).order_by("name")
        children = list(containers) + list(items)

    elif isinstance(node, Container):
        containers = Container.objects.filter(parent_container=node).order_by("name")
        items = Item.objects.filter(container=node).order_by("name")
        children = list(containers) + list(items)

    # Item: return empty list

    return children


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_node(request, node_type, node_id):
    try:
        if node_type == 'home':
            node = Home.objects.get(pk=node_id)
            # Unlike room/container/item (pre-existing AllowAny gap, left as-is),
            # a home's full room listing is sensitive enough to gate explicitly.
            if not request.user.is_authenticated or not HomeMembership.objects.filter(
                user=request.user, home=node
            ).exists():
                return Response(
                    {"message": f"home with id {node_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif node_type == 'room':
            node = Room.objects.get(pk=node_id)
        elif node_type == 'container':
            node = Container.objects.get(pk=node_id)
        elif node_type == 'item':
            node = Item.objects.get(pk=node_id)
        else:
            return Response(
                {"message": "Invalid node_type"},
                status=status.HTTP_400_BAD_REQUEST
            )
    except ObjectDoesNotExist:
        return Response(
            {"message": f"{node_type} with id {node_id} not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    # Looks at the node instance, finds its name attribute, and produces this JSON shape: { "name": "kitchen" }
    if node_type == 'item':
        is_starred = request.user.is_authenticated and StarredItem.objects.filter(user=request.user, item=node).exists()
        node_details = ItemNodeDetailsSerializer(node, context={'request': request, 'is_starred': is_starred})
    elif node_type == 'home':
        node_details = HomeSerializer(node, context={'user': request.user})
    else:
        is_starred = request.user.is_authenticated and _STAR_MODEL_BY_TYPE[node_type].objects.filter(
            user=request.user, **{node_type: node}
        ).exists()
        node_details = NodeDetailsSerializer(node, context={'is_starred': is_starred})

    # Looks at the node instances, extracts the fields declared in ChildSerializer, returns the JSON.
    # DRF needs many=True when serializing multiple objects.
    children_list = determine_children(node)
    starred_keys = get_starred_keys(request.user, children_list) if request.user.is_authenticated else set()
    children = ChildSerializer(children_list, many=True, context={'starred_keys': starred_keys})

    return Response(
        {
            "node_details": node_details.data,
            "children": children.data
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
def create_room(request):
    """Create a Room directly under a Home. Any member of the home may do this."""
    home_id = request.data.get('home_id')
    name = (request.data.get('name') or '').strip()
    description = request.data.get('description') or None

    if not home_id or not name:
        return Response({"message": "home_id and name are required."}, status=status.HTTP_400_BAD_REQUEST)

    if not HomeMembership.objects.filter(user=request.user, home_id=home_id).exists():
        return Response({"message": f"Home with id {home_id} not found."}, status=status.HTTP_404_NOT_FOUND)

    room = Room.objects.create(name=name, description=description, home_id=home_id, created_by=request.user)
    return Response({"status": "ok", "id": room.id}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def create_container(request):
    """
    Create a Container under a Room (level 1) or another Container (level =
    parent.level + 1, capped at 5). Any member of the owning home may do this.
    """
    name = (request.data.get('name') or '').strip()
    description = request.data.get('description') or None
    room_id = request.data.get('room_id')
    parent_container_id = request.data.get('parent_container_id')

    if not name:
        return Response({"message": "name is required."}, status=status.HTTP_400_BAD_REQUEST)

    if bool(room_id) == bool(parent_container_id):
        return Response(
            {"message": "Exactly one of room_id or parent_container_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if room_id:
        try:
            room = Room.objects.get(pk=room_id)
        except ObjectDoesNotExist:
            return Response({"message": f"Room with id {room_id} not found."}, status=status.HTTP_404_NOT_FOUND)
        home_id = room.home_id
        level = 1
        create_kwargs = {"room": room}
    else:
        try:
            parent = Container.objects.get(pk=parent_container_id)
        except ObjectDoesNotExist:
            return Response(
                {"message": f"Container with id {parent_container_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if parent.level >= 5:
            return Response(
                {"message": "Containers cannot be nested deeper than 5 levels."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        home_tag = resolve_container_home(parent)
        home_id = home_tag[0] if home_tag else None
        level = parent.level + 1
        create_kwargs = {"parent_container": parent}

    if not home_id or not HomeMembership.objects.filter(user=request.user, home_id=home_id).exists():
        return Response({"message": "Parent not found."}, status=status.HTTP_404_NOT_FOUND)

    container = Container.objects.create(
        name=name, description=description, level=level, created_by=request.user, **create_kwargs
    )
    return Response({"status": "ok", "id": container.id}, status=status.HTTP_201_CREATED)


def _duplicate_item_name(name, room=None, container=None, exclude_id=None):
    """Whether another Item with this name already lives in the same room/container."""
    qs = Item.objects.filter(name=name, room=room) if room else Item.objects.filter(name=name, container=container)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


@api_view(['POST'])
def create_item(request):
    """Create an Item under a Room or a Container. Any member of the owning home may do this."""
    name = (request.data.get('name') or '').strip()
    room_id = request.data.get('room_id')
    container_id = request.data.get('container_id')

    if not name:
        return Response({"message": "name is required."}, status=status.HTTP_400_BAD_REQUEST)

    if bool(room_id) == bool(container_id):
        return Response(
            {"message": "Exactly one of room_id or container_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if room_id:
        try:
            room = Room.objects.get(pk=room_id)
        except ObjectDoesNotExist:
            return Response({"message": f"Room with id {room_id} not found."}, status=status.HTTP_404_NOT_FOUND)
        home_id = room.home_id
        create_kwargs = {"room": room}
    else:
        try:
            container = Container.objects.get(pk=container_id)
        except ObjectDoesNotExist:
            return Response(
                {"message": f"Container with id {container_id} not found."}, status=status.HTTP_404_NOT_FOUND
            )
        home_tag = resolve_container_home(container)
        home_id = home_tag[0] if home_tag else None
        create_kwargs = {"container": container}

    if not home_id or not HomeMembership.objects.filter(user=request.user, home_id=home_id).exists():
        return Response({"message": "Parent not found."}, status=status.HTTP_404_NOT_FOUND)

    if _duplicate_item_name(name, **create_kwargs):
        return Response(
            {"message": f'An item named "{name}" already exists here.'}, status=status.HTTP_400_BAD_REQUEST
        )

    item = Item.objects.create(
        name=name,
        description=request.data.get('description') or None,
        quantity=request.data.get('quantity') or 1,
        category=request.data.get('category') or None,
        expiration_date=request.data.get('expiration_date') or None,
        comment=request.data.get('comment') or None,
        tags=request.data.get('tags') or None,
        picture=request.data.get('picture') or None,
        created_by=request.user,
        **create_kwargs,
    )
    return Response({"status": "ok", "id": item.id}, status=status.HTTP_201_CREATED)


def _get_member_node_or_error(request, node_type, node_id):
    """
    Look up a Room/Container/Item by id and confirm the requester is a member
    of its owning home. Returns (node, None) on success, or (None,
    error_response) otherwise.
    """
    if node_type == 'room':
        try:
            node = Room.objects.get(pk=node_id)
        except ObjectDoesNotExist:
            return None, Response({"message": f"Room with id {node_id} not found."}, status=status.HTTP_404_NOT_FOUND)
        home_id = node.home_id
    elif node_type == 'container':
        try:
            node = Container.objects.get(pk=node_id)
        except ObjectDoesNotExist:
            return None, Response(
                {"message": f"Container with id {node_id} not found."}, status=status.HTTP_404_NOT_FOUND
            )
        home_tag = resolve_container_home(node)
        home_id = home_tag[0] if home_tag else None
    elif node_type == 'item':
        try:
            node = Item.objects.get(pk=node_id)
        except ObjectDoesNotExist:
            return None, Response({"message": f"Item with id {node_id} not found."}, status=status.HTTP_404_NOT_FOUND)
        home_id = get_home_id_for_item(node)
    else:
        return None, Response({"message": "Invalid node_type"}, status=status.HTTP_400_BAD_REQUEST)

    if not home_id or not HomeMembership.objects.filter(user=request.user, home_id=home_id).exists():
        return None, Response({"message": f"{node_type} with id {node_id} not found."}, status=status.HTTP_404_NOT_FOUND)

    return node, None


_STAR_MODEL_BY_TYPE = {'room': StarredRoom, 'container': StarredContainer, 'item': StarredItem}
_NODE_MODEL_BY_TYPE = {'room': Room, 'container': Container, 'item': Item}


def _updated_at_matches(current, expected):
    """
    Compare two aware datetimes for the optimistic-concurrency check,
    truncated to millisecond precision. The mobile client round-trips
    updated_at through a JS Date, which only carries millisecond precision,
    so comparing at full microsecond precision would falsely flag every
    edit as stale.
    """
    to_ms = lambda dt: dt.replace(microsecond=(dt.microsecond // 1000) * 1000)
    return to_ms(current) == to_ms(expected)


def _optimistic_lock_or_error(model, pk, expected_updated_at, label):
    """
    Must be called inside transaction.atomic(). Re-fetches the row with
    select_for_update() to close the TOCTOU race between reading updated_at
    and writing it (a plain read-then-compare-then-save can let two
    near-simultaneous requests both pass the check). If expected_updated_at
    is falsy, the caller's request predates this field (see OCC spec Sec 2)
    and the check is skipped entirely. Returns (locked_instance, None) on
    success, or (None, error_response) on conflict/not-found/malformed input.
    """
    try:
        locked = model.objects.select_for_update().get(pk=pk)
    except ObjectDoesNotExist:
        return None, Response(
            {"message": f"{label} with id {pk} not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if expected_updated_at:
        expected = parse_datetime(expected_updated_at) if isinstance(expected_updated_at, str) else None
        if expected is None:
            return None, Response(
                {"message": "expected_updated_at is not a valid ISO-8601 datetime."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not _updated_at_matches(locked.updated_at, expected):
            return None, Response(
                {
                    "message": f"This {label} has been changed since you loaded it. "
                               "Please refresh and try again."
                },
                status=status.HTTP_409_CONFLICT,
            )

    return locked, None


def get_starred_keys(user, nodes):
    """
    Which of `nodes` (a mixed list of raw Room/Container/Item instances) the
    user has starred. Returns a set of (type_str, id) tuples, batched into
    one query per node_type rather than one query per node to avoid N+1s
    when serializing a children/search list.
    """
    room_ids = [n.id for n in nodes if isinstance(n, Room)]
    container_ids = [n.id for n in nodes if isinstance(n, Container)]
    item_ids = [n.id for n in nodes if isinstance(n, Item)]

    keys = set()
    keys |= {
        ('room', i) for i in StarredRoom.objects.filter(user=user, room_id__in=room_ids).values_list('room_id', flat=True)
    }
    keys |= {
        ('container', i)
        for i in StarredContainer.objects.filter(user=user, container_id__in=container_ids).values_list(
            'container_id', flat=True
        )
    }
    keys |= {
        ('item', i) for i in StarredItem.objects.filter(user=user, item_id__in=item_ids).values_list('item_id', flat=True)
    }
    return keys


@api_view(['POST'])
def rename_node(request, node_type, node_id):
    """Rename a Room, Container, or Item. Any member of the owning home may do this."""
    node, error = _get_member_node_or_error(request, node_type, node_id)
    if error:
        return error

    name = (request.data.get('name') or '').strip()
    if not name:
        return Response({"message": "name is required."}, status=status.HTTP_400_BAD_REQUEST)

    if node_type == 'item' and _duplicate_item_name(name, room=node.room, container=node.container, exclude_id=node.id):
        return Response(
            {"message": f'An item named "{name}" already exists here.'}, status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        node, error = _optimistic_lock_or_error(
            _NODE_MODEL_BY_TYPE[node_type], node.pk, request.data.get('expected_updated_at'), node_type
        )
        if error:
            return error
        node.name = name
        node.save()

    if node_type == 'item':
        is_starred = StarredItem.objects.filter(user=request.user, item=node).exists()
        node_details = ItemNodeDetailsSerializer(node, context={'request': request, 'is_starred': is_starred})
    else:
        is_starred = _STAR_MODEL_BY_TYPE[node_type].objects.filter(user=request.user, **{node_type: node}).exists()
        node_details = NodeDetailsSerializer(node, context={'is_starred': is_starred})

    return Response(node_details.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def delete_node(request, node_type, node_id):
    """
    Delete a Room, Container, or Item. Any member of the owning home may do
    this. Room/Container deletes clean up descendant Items explicitly first —
    Item.room/Item.container are SET_NULL (not CASCADE), so left to Django's
    cascade collector they'd survive as orphans with both fields null.
    """
    node, error = _get_member_node_or_error(request, node_type, node_id)
    if error:
        return error

    if node_type == 'room':
        container_ids = get_container_ids_under_room(node)
        items = Item.objects.filter(Q(room=node) | Q(container_id__in=container_ids))
        for picture in items.values_list('picture', flat=True):
            if picture:
                delete_item_photo(picture)
        items.delete()
    elif node_type == 'container':
        container_ids = get_container_subtree_ids(node)
        items = Item.objects.filter(container_id__in=container_ids)
        for picture in items.values_list('picture', flat=True):
            if picture:
                delete_item_photo(picture)
        items.delete()
    elif node.picture:  # item: a leaf, no descendant cleanup needed.
        delete_item_photo(node.picture)

    node.delete()
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def star_node(request, node_type, node_id):
    """Star (favorite) a Room, Container, or Item. Any member of the owning home may do this. Idempotent."""
    node, error = _get_member_node_or_error(request, node_type, node_id)
    if error:
        return error

    _STAR_MODEL_BY_TYPE[node_type].objects.get_or_create(user=request.user, **{node_type: node})
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def unstar_node(request, node_type, node_id):
    """Unstar a Room, Container, or Item. Any member of the owning home may do this. Idempotent."""
    node, error = _get_member_node_or_error(request, node_type, node_id)
    if error:
        return error

    _STAR_MODEL_BY_TYPE[node_type].objects.filter(user=request.user, **{node_type: node}).delete()
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def update_item(request, item_id):
    """
    Partially update an Item: only fields present in the request body are
    touched (the frontend edits one field at a time from the detail page),
    everything else on the item is left untouched. Any member of the owning
    home may do this.
    """
    item, error = _get_member_node_or_error(request, 'item', item_id)
    if error:
        return error

    data = request.data

    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return Response({"message": "name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if _duplicate_item_name(name, room=item.room, container=item.container, exclude_id=item.id):
            return Response(
                {"message": f'An item named "{name}" already exists here.'}, status=status.HTTP_400_BAD_REQUEST
            )
    if 'quantity' in data:
        new_quantity = data.get('quantity') or 1
        checked_out = sum(item.checkouts.values_list('quantity', flat=True))
        if new_quantity < checked_out:
            return Response(
                {"message": f"Cannot set quantity below the {checked_out} already checked out."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    old_picture = None
    with transaction.atomic():
        item, error = _optimistic_lock_or_error(Item, item.pk, data.get('expected_updated_at'), 'item')
        if error:
            return error

        if 'name' in data:
            item.name = name
        if 'description' in data:
            item.description = data.get('description') or None
        if 'quantity' in data:
            item.quantity = new_quantity
        if 'category' in data:
            item.category = data.get('category') or None
        if 'expiration_date' in data:
            item.expiration_date = data.get('expiration_date') or None
        if 'comment' in data:
            item.comment = data.get('comment') or None
        if 'tags' in data:
            item.tags = data.get('tags') or None
        if 'picture' in data:
            new_picture = data.get('picture') or None
            if item.picture and item.picture != new_picture:
                old_picture = item.picture
            item.picture = new_picture

        item.save()

    # Deleted only after the transaction commits, so the S3 call (network
    # I/O) doesn't extend how long the row lock above is held.
    if old_picture:
        delete_item_photo(old_picture)

    return Response(ItemNodeDetailsSerializer(item, context={'request': request}).data, status=status.HTTP_200_OK)


@api_view(['POST'])
def presign_item_photo(request, item_id):
    """
    Mint a presigned S3 PUT URL for uploading a photo for an item. Any
    member of the owning home may do this. The client uploads directly to
    S3 with the returned URL, then persists `photo_url` via update_item.
    """
    item, error = _get_member_node_or_error(request, 'item', item_id)
    if error:
        return error

    content_type = request.data.get('content_type')
    if content_type not in ALLOWED_PHOTO_CONTENT_TYPES:
        return Response({"message": "Unsupported content type."}, status=status.HTTP_400_BAD_REQUEST)

    upload_url, photo_url, expires_in = presign_item_photo_upload(item.id, content_type)

    return Response(
        {"upload_url": upload_url, "photo_url": photo_url, "expires_in": expires_in},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
def delete_item_photo_view(request, item_id):
    """
    Delete the item's current photo, both from S3 and from the item record.
    Any member of the owning home may do this.
    """
    item, error = _get_member_node_or_error(request, 'item', item_id)
    if error:
        return error

    if item.picture:
        delete_item_photo(item.picture)
        item.picture = None
        item.save()

    return Response(ItemNodeDetailsSerializer(item, context={'request': request}).data, status=status.HTTP_200_OK)


@api_view(['POST'])
def checkout_item(request, item_id):
    """Check out a quantity of an Item for the requesting user. Any member of the owning home may do this."""
    item, error = _get_member_node_or_error(request, 'item', item_id)
    if error:
        return error

    try:
        quantity = int(request.data.get('quantity'))
    except (TypeError, ValueError):
        return Response({"message": "quantity is required."}, status=status.HTTP_400_BAD_REQUEST)

    if quantity <= 0:
        return Response({"message": "quantity must be greater than 0."}, status=status.HTTP_400_BAD_REQUEST)

    checked_out = sum(item.checkouts.values_list('quantity', flat=True))
    available = item.quantity - checked_out
    if quantity > available:
        return Response({"message": f"Only {available} available to check out."}, status=status.HTTP_400_BAD_REQUEST)

    checkout, created = ItemCheckout.objects.get_or_create(item=item, user=request.user, defaults={'quantity': quantity})
    if not created:
        checkout.quantity += quantity
        checkout.save()

    return Response(ItemNodeDetailsSerializer(item, context={'request': request}).data, status=status.HTTP_200_OK)


@api_view(['POST'])
def return_item_checkout(request, item_id):
    """
    Return some or all of a checked-out quantity, adding it back to the
    item's available quantity. A user may return their own checkout; the
    home's creator may return anyone's.
    """
    item, error = _get_member_node_or_error(request, 'item', item_id)
    if error:
        return error

    user_id = request.data.get('user_id') or request.user.id

    if str(user_id) != str(request.user.id):
        home_id = get_home_id_for_item(item)
        home = Home.objects.filter(pk=home_id).first() if home_id else None
        if not home or home.created_by_id != request.user.id:
            return Response(
                {"message": "Only the checkout owner or the home's creator can return this."},
                status=status.HTTP_403_FORBIDDEN,
            )

    try:
        quantity = int(request.data.get('quantity'))
    except (TypeError, ValueError):
        return Response({"message": "quantity is required."}, status=status.HTTP_400_BAD_REQUEST)

    if quantity <= 0:
        return Response({"message": "quantity must be greater than 0."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        checkout = ItemCheckout.objects.get(item=item, user_id=user_id)
    except ItemCheckout.DoesNotExist:
        return Response({"message": "No checked-out quantity found for that user."}, status=status.HTTP_404_NOT_FOUND)

    if quantity > checkout.quantity:
        return Response({"message": f"Only {checkout.quantity} checked out."}, status=status.HTTP_400_BAD_REQUEST)

    if quantity == checkout.quantity:
        checkout.delete()
    else:
        checkout.quantity -= quantity
        checkout.save()

    return Response(ItemNodeDetailsSerializer(item, context={'request': request}).data, status=status.HTTP_200_OK)


@api_view(['GET'])
def search_nodes(request):
    """
    Search rooms/containers/items the user has access to.

    Rooms and containers match on name only. Items also match on category
    and tags, since those are searchable item attributes.

    Query params:
      q: search text (required)
      scope: 'folder' | 'everywhere' (required)
      origin_type: 'home' | 'room' | 'container' (required when scope='folder')
      origin_id: int (required when scope='folder')
    """
    q = request.GET.get('q', '').strip()
    scope = request.GET.get('scope')
    origin_type = request.GET.get('origin_type')
    origin_id = request.GET.get('origin_id')

    if not q:
        return Response({"message": "q is required."}, status=status.HTTP_400_BAD_REQUEST)
    if scope not in ('folder', 'everywhere'):
        return Response({"message": "scope must be 'folder' or 'everywhere'."}, status=status.HTTP_400_BAD_REQUEST)
    if scope == 'folder' and (not origin_type or origin_id is None):
        return Response(
            {"message": "origin_type and origin_id are required when scope='folder'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    origin_id_int = None
    if origin_id is not None:
        try:
            origin_id_int = int(origin_id)
        except (TypeError, ValueError):
            return Response({"message": "origin_id must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result_scope = resolve_search_scope(request.user, scope, origin_type, origin_id_int)
    except ValueError:
        return Response({"message": "Origin not found or not accessible."}, status=status.HTTP_404_NOT_FOUND)

    home_by_room = result_scope['home_by_room']
    home_by_container = result_scope['home_by_container']

    rooms = list(Room.objects.filter(id__in=result_scope['match_room_ids'], name__icontains=q))
    containers = list(Container.objects.filter(id__in=result_scope['match_container_ids'], name__icontains=q))

    # tags is a Postgres array field, so matching q against individual tags
    # needs unnest() rather than a plain __icontains lookup (which only
    # supports whole-array membership checks, not substrings). unnest() has
    # to live inside a correlated EXISTS subquery rather than directly in
    # WHERE, since Postgres disallows set-returning functions there.
    #
    # ILIKE's own wildcards (%, _) need escaping so a literal % or _ in q is
    # matched literally, same as name__icontains/category__icontains already
    # do under the hood.
    escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    tag_match = RawSQL(
        "EXISTS (SELECT 1 FROM unnest(tags) AS tag WHERE tag ILIKE %s)",
        (f"%{escaped_q}%",),
        output_field=BooleanField(),
    )

    items = list(Item.objects.annotate(tag_match=tag_match).filter(
        Q(room_id__in=result_scope['item_room_ids']) | Q(container_id__in=result_scope['item_container_ids']),
    ).filter(
        Q(name__icontains=q) | Q(category__icontains=q) | Q(tag_match=True)
    ))

    for r in rooms:
        r.home_id, r.home_name = home_by_room[r.id]
    for c in containers:
        c.home_id, c.home_name = home_by_container[c.id]
    for i in items:
        i.home_id, i.home_name = home_by_room.get(i.room_id) or home_by_container.get(i.container_id)

    # Defensive cap, matching the no-pagination style of get_node/get_places_tab.
    results = (rooms + containers + items)[:50]
    serialized = SearchResultSerializer(results, many=True, context={'starred_keys': get_starred_keys(request.user, results)})

    return Response(
        {"query": q, "scope": scope, "results": serialized.data},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
def checked_out_items(request):
    """All items the requesting user currently has checked out, across every home they belong to."""
    checkouts = ItemCheckout.objects.filter(user=request.user).select_related(
        'item', 'item__room__home', 'item__container'
    )

    items = []
    for checkout in checkouts:
        item = checkout.item
        item.checked_out_quantity = checkout.quantity
        if item.room_id:
            item.home_id, item.home_name = item.room.home_id, item.room.home.name
        else:
            item.home_id, item.home_name = resolve_container_home(item.container)
        items.append(item)

    serialized = CheckedOutItemSerializer(items, many=True)

    return Response({"results": serialized.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
def starred_nodes(request):
    """
    All rooms/containers/items the requesting user has starred, across every
    home they're currently a member of. Scoped to current membership (rather
    than trusting the StarredX rows alone) because a star isn't cleaned up if
    the user's access to that home is later revoked.
    """
    user_home_ids = get_home_ids_for_user(request.user)
    nodes = []

    for starred in StarredRoom.objects.filter(user=request.user, room__home_id__in=user_home_ids).select_related(
        'room__home'
    ):
        room = starred.room
        room.home_id, room.home_name = room.home_id, room.home.name
        nodes.append(room)

    for starred in StarredContainer.objects.filter(user=request.user).select_related('container'):
        container = starred.container
        home_tag = resolve_container_home(container)
        if not home_tag or home_tag[0] not in user_home_ids:
            continue
        container.home_id, container.home_name = home_tag
        nodes.append(container)

    for starred in StarredItem.objects.filter(user=request.user).select_related('item__room__home', 'item__container'):
        item = starred.item
        home_id = get_home_id_for_item(item)
        if home_id not in user_home_ids:
            continue
        if item.room_id:
            item.home_id, item.home_name = item.room.home_id, item.room.home.name
        else:
            item.home_id, item.home_name = resolve_container_home(item.container)
        nodes.append(item)

    serialized = StarredNodeSerializer(nodes, many=True)

    return Response({"results": serialized.data}, status=status.HTTP_200_OK)


@api_view(['POST'])
def create_home(request):
    """Create a Home for the authenticated user.

    The user becomes a member via HomeMembership. If the user has no
    primary_home yet, this home is set as their primary home.
    """
    name = request.data.get('name')
    if not name or not name.strip():
        return Response({"message": "name is required."}, status=status.HTTP_400_BAD_REQUEST)

    address = request.data.get('address')
    user = request.user

    home = Home.objects.create(name=name.strip(), address=address, created_by=user)
    HomeMembership.objects.create(user=user, home=home)

    if user.primary_home is None:
        user.primary_home = home
        user.save()

    return Response(
        HomeSerializer(home, context={'user': user}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
def set_primary_home(request):
    """Set the authenticated user's primary_home to a home they are a member of."""
    home_id = request.data.get('home_id')
    if not home_id:
        return Response({"message": "home_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    membership = HomeMembership.objects.filter(user=user, home_id=home_id).first()
    if not membership:
        return Response(
            {"message": f"Home with id {home_id} not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user.primary_home = membership.home
    user.save()

    return Response({"status": "ok", "primary_home": user.primary_home.id}, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_homes(request):
    """Return every Home the authenticated user is a member of."""
    memberships = [m.home for m in HomeMembership.objects.filter(user=request.user)]
    homes = HomeSerializer(memberships, context={'user': request.user}, many=True)
    return Response({"homes": homes.data}, status=status.HTTP_200_OK)


def _get_creator_home_or_error(request, home_id):
    """
    Look up a Home by id and confirm the requester is its creator.
    Returns (home, None) on success, or (None, error_response) otherwise.
    """
    try:
        home = Home.objects.get(pk=home_id)
    except ObjectDoesNotExist:
        return None, Response(
            {"message": f"Home with id {home_id} not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if home.created_by_id != request.user.id:
        return None, Response(
            {"message": "Only the home's creator can do this."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return home, None


@api_view(['POST'])
def rename_home(request, home_id):
    home, error = _get_creator_home_or_error(request, home_id)
    if error:
        return error

    name = (request.data.get('name') or '').strip()
    if not name:
        return Response({"message": "name is required."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        home, error = _optimistic_lock_or_error(Home, home.pk, request.data.get('expected_updated_at'), 'home')
        if error:
            return error
        home.name = name
        home.save()

    return Response(HomeSerializer(home, context={'user': request.user}).data, status=status.HTTP_200_OK)


@api_view(['POST'])
def update_home_address(request, home_id):
    home, error = _get_creator_home_or_error(request, home_id)
    if error:
        return error

    with transaction.atomic():
        home, error = _optimistic_lock_or_error(Home, home.pk, request.data.get('expected_updated_at'), 'home')
        if error:
            return error
        home.address = request.data.get('address') or None
        home.save()

    return Response(HomeSerializer(home, context={'user': request.user}).data, status=status.HTTP_200_OK)


@api_view(['POST'])
def delete_home(request, home_id):
    home, error = _get_creator_home_or_error(request, home_id)
    if error:
        return error

    # Room/Container cascade-delete when their Home/Room is deleted, but
    # Item.room/Item.container are SET_NULL — left to Django's cascade
    # collector, items would survive as orphans with both fields null,
    # violating Item.clean()'s "must belong to room or container" invariant.
    # Delete them explicitly first. Containers can be nested up to 5 levels,
    # so a plain `container__room__home` match only catches level-1 containers
    # — walk the full subtree to also catch items nested deeper.
    container_ids = get_container_ids_for_home(home)
    Item.objects.filter(Q(room__home=home) | Q(container_id__in=container_ids)).delete()
    home.delete()

    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def share_home(request, home_id):
    home, error = _get_creator_home_or_error(request, home_id)
    if error:
        return error

    username = (request.data.get('username') or '').strip()
    if not username:
        return Response({"message": "username is required."}, status=status.HTTP_400_BAD_REQUEST)

    target_user = CustomUser.objects.filter(username__iexact=username).first()
    if not target_user:
        return Response({"message": f"No user with username '{username}'."}, status=status.HTTP_404_NOT_FOUND)

    if HomeMembership.objects.filter(user=target_user, home=home).exists():
        return Response(
            {"message": f"{target_user.username} is already a member of this home."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    HomeMembership.objects.create(user=target_user, home=home)
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_home_members(request, home_id):
    home, error = _get_creator_home_or_error(request, home_id)
    if error:
        return error

    members = [
        {"id": m.user.id, "username": m.user.username}
        for m in HomeMembership.objects.filter(home=home).select_related('user')
    ]
    return Response({"members": members}, status=status.HTTP_200_OK)


@api_view(['POST'])
def remove_home_member(request, home_id):
    home, error = _get_creator_home_or_error(request, home_id)
    if error:
        return error

    user_id = request.data.get('user_id')
    if not user_id:
        return Response({"message": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    if str(user_id) == str(home.created_by_id):
        return Response(
            {"message": "The creator cannot be removed. Delete the home instead."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    deleted, _ = HomeMembership.objects.filter(home=home, user_id=user_id).delete()
    if not deleted:
        return Response({"message": "That user is not a member of this home."}, status=status.HTTP_404_NOT_FOUND)

    return Response({"status": "ok"}, status=status.HTTP_200_OK)
