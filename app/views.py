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
from django.shortcuts import render
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework import serializers, permissions
from django.core.mail import send_mail
from django.core.signing import TimestampSigner
from datetime import timedelta, datetime
from django.contrib.auth import authenticate
from django.db.models import Q
import time
# from .services import place_node_helpers
from .services.search_helpers import resolve_search_scope

from .models import CustomUser, PasswordResetToken, Room, Container, Item, Home, HomeMembership
from .serializers import RegisterSerializer, IdentifySerializer, LoginSerializer, ResetPasswordSerializer, SetPasswordSerializer, ChildSerializer, NodeDetailsSerializer, ItemNodeDetailsSerializer, HomeSerializer, RoomSerializer, SearchResultSerializer
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
            email = serializer.validated_data['email'].lower()
            password = serializer.validated_data['password']

            user = authenticate(email=email, password=password)

            if user and user.email_verified:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'id': user.id,
                    'email': user.email,
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
                return Response({'message': 'Email or password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)

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
        )
    elif user.google_email != idInfo['email'].lower():
        user.google_email = idInfo['email'].lower()
        user.save()

    refresh = RefreshToken.for_user(user)
    return Response({
        "status": "ok",
        "name": idInfo.get('name'),
        "email": user.email,
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
    )
    refresh = RefreshToken.for_user(user)
    return Response({
        "status": "ok",
        "email": user.email,
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

    if isinstance(node, Room):
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
        if node_type == 'room':
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
        node_details = ItemNodeDetailsSerializer(node)
    else:
        node_details = NodeDetailsSerializer(node)
    # Looks at the node instances, extracts the fields declared in ChildSerializer, returns the JSON.
    # DRF needs many=True when serializing multiple objects.
    children = ChildSerializer(determine_children(node), many=True)

    return Response(
        {
            "node_details": node_details.data,
            "children": children.data
        },
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
def search_nodes(request):
    """
    Search rooms/containers/items the user has access to.

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
    items = list(Item.objects.filter(
        Q(room_id__in=result_scope['item_room_ids']) | Q(container_id__in=result_scope['item_container_ids']),
        name__icontains=q,
    ))

    for r in rooms:
        r.home_id, r.home_name = home_by_room[r.id]
    for c in containers:
        c.home_id, c.home_name = home_by_container[c.id]
    for i in items:
        i.home_id, i.home_name = home_by_room.get(i.room_id) or home_by_container.get(i.container_id)

    # Defensive cap, matching the no-pagination style of get_node/get_places_tab.
    results = (rooms + containers + items)[:50]
    serialized = SearchResultSerializer(results, many=True)

    return Response(
        {"query": q, "scope": scope, "results": serialized.data},
        status=status.HTTP_200_OK
    )


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
def get_places_tab(request, home_id):
    try:
        home = Home.objects.get(pk=home_id)
        home_details = HomeSerializer(home, context={'user': request.user})

        memberships = [m.home for m in HomeMembership.objects.filter(user=request.user)]
        homes = HomeSerializer(memberships, context={'user': request.user}, many=True)
        rooms = RoomSerializer(Room.objects.filter(home=home), many=True)
    except ObjectDoesNotExist:
        return Response(
            {"message": f"Home with id {home_id} not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    ret = {
        "home_details": home_details.data,
        "rooms": rooms.data,
        "homes": homes.data
    }

    return Response(ret, status=status.HTTP_200_OK)
