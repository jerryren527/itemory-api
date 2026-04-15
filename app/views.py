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
from google.auth.transport import requests
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
import time
from .services import place_node_helpers

from .models import CustomUser, PasswordResetToken, Room, Container, Item, Home, HomeMembership
from .serializers import RegisterSerializer, IdentifySerializer, LoginSerializer,  ResetPasswordSerializer, ChildSerializer, NodeDetailsSerializer, HomeSerializer, RoomSerializer
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
    print(os.environ)
    # print("=== INSIDE login() ===")
    # time.sleep(10)
    try:
        # email = request.data.get('email')
        # password = request.data.get('password')
        attrs = {
            'email': request.data.get('email'),
            'password': request.data.get('password'),
        }
        # print(attrs)

        # request.data is the request payload sent with the HTTP request to 'app/login'.
        # Without 'data=request.data', is_valid() throws an error, and you have no access to validated_data.
        serializer = LoginSerializer(data=request.data)

        # serializer.is_valid(raise_exception=True)
        if serializer.is_valid():
            # print('serializer.validated_data:', serializer.validated_data)
            # Throws ValidationError if invalid email or password. Attaches 'users' to attrs if valid email and password.
            serializer.validate(attrs)

            user = serializer.validated_data

            email = attrs['email'].lower()  # lowercase the user's input
            password = attrs['password']

            # django.contrib.auth.authenticate is case-sensitive, that is why we lowercased email.
            user = authenticate(
                # request=request.context.get('request'),
                email=email,
                password=password
            )

            # print('user', user)

            # check if the user's email address is verififed
            if user and user.email_verified:
                print(f'user: {user}')
                print(f'type(user): {type(user)}')
                print(f'user.has_password: {user.has_password}')
                print(f'user.email_verified: {user.email_verified}')
                print(
                    f'user.google_account_linked: {user.google_account_linked}')
                print(f'user.primary_home: {user.primary_home}')

                # print('user email address is verified')
                # Create tokens
                refresh = RefreshToken.for_user(user)

                # send tokens
                res = {
                    'id': user.id,
                    'email': user.email,
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    },
                    'has_password': user.has_password,
                    'email_verified': user.email_verified,
                    'google_account_linked': user.google_account_linked,
                    'primary_home': user.primary_home.id if user.primary_home else None,
                }
                return Response(res, status=status.HTTP_200_OK)
            elif user and not user.email_verified and not user.google_account_linked:
                # User's email is not verified, and they are not a google-only user
                res = {
                    'message': 'Email addresss is not verified yet.'
                }
                return Response(res, status=status.HTTP_401_UNAUTHORIZED)
            elif user and not user.email_verified and user.google_account_linked:
                res = {
                    'message': f'{email} is a Google-only user and has not set up a password yet. Sign in with Google.'
                }
                return Response(res, status=status.HTTP_401_UNAUTHORIZED)

            else:
                # Check that the user is a Google-only user
                # user_queryset = CustomUser.objects.filter(email=email)
                # if len(user_queryset) == 1 and user_queryset[0].google_account_linked and not user_queryset[0].has_password:
                #     res = {
                #         'message': f'{email} is a Google-only user and has not set up a password yet. Sign in with Google.'
                #     }
                res = {
                    'message': 'Email or password is incorrect.'
                }
                return Response(res, status=status.HTTP_401_UNAUTHORIZED)

        else:
            print('LoginSerializer had invalid input.')
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

    except serializers.ValidationError as err:
        # TODO: flatten ValidationError message before sending to client
        # print('There was a ValidationError:', err.detail['non_field_errors'][0])

        # Get the ValidationError's message
        res = {
            'message': f"{str(err.detail['non_field_errors'][0])}",
        }

        return Response(res, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as err:
        # print('Unknown Error:', err)

        res = {
            'message': f"{err}",
        }

        # return Response(res, status=status.HTTP_400_BAD_REQUEST)
        return Response(res, status=status.HTTP_401_UNAUTHORIZED)


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
                # register_serializer.send_verification_email(new_user)

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
            if not user.email_verified:
                if user.google_account_linked:
                    # Account with this email already exists. Find out if they have Google Sign In auth option.
                    res = {
                        'message': 'This email is already linked to Google. Please Log in with Google.',
                        'user_has_google': user.google_account_linked
                    }
                    return Response(res, status=status.HTTP_409_CONFLICT)
                else:
                    # if the email is not verified yet, still send the verification email.
                    # print('The email is not verified yet. Sending another verification email.')
                    register_serializer.send_verification_email(user)

                    res = {
                        'message': 'Verification Email sent!'
                    }

                    return Response(res, status=status.HTTP_200_OK)
            else:
                res = {
                    "message": "An account with this email address already exists."
                }

                return Response(res, status=status.HTTP_409_CONFLICT)

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
    # Authorize Google User
    print("INSIDE AUTHORIZE_USER")

    print(request)

    print('request.data:', request.data)
    idToken = request.data.get('idToken')

    try:
        # print('os.getenv("GOOGLE_WEB_CLIENT_ID"):',
        #       os.getenv('GOOGLE_WEB_CLIENT_ID'))
        idInfo = id_token.verify_oauth2_token(idToken, requests.Request(
        ), os.getenv('GOOGLE_WEB_CLIENT_ID'))
        # print('idInfo:', idInfo)
        # print('type(idInfo):', type(idInfo))

        if idInfo['email_verified'] == False:
            res = {
                "messsge": "Invalid Google Email"
            }
            return Response(res, status=status.HTTP_400_BAD_REQUEST)

        # the unique identifier is the email address.
        # handle when email already exists through google log in.
        # Decision for now: the emails must match -- the google email address that the user wants to link must match the email address they are currently signed in as.

        # check if email address already exists in CustomUser table
        # Model.MultipleObjectsReturned exception if .get() returns multiple matches
        # Raises a Model.DoesNotExist exception if not matches.
        # Will use filter instead and get the length of the QuerySet instead of throwing an exception.
        # user = CustomUser.objects.get(email=idInfo['email'])
        user_query = CustomUser.objects.filter(email=idInfo['email'])
        print('user_query:', user_query)

        if len(user_query) == 1:
            print(f'user, {idInfo['email']}, is defined.')
            user = user_query[0]

            print(idInfo)
            if not user.google_sub and user.google_account_linked == False:
                print('google_account_linked is false.')
                user.google_account_linked = True
                user.google_picture_url = idInfo['picture']
                user.google_sub = idInfo['sub']
                user.save()

            print('====Creating access and refresh tokens...====')
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token

            print('refresh: ', refresh)
            print('access: ', access)

            res = {
                "name": idInfo['name'],
                "email": idInfo['email'],
                "picture": idInfo['picture'],
                "google_sub": idInfo['sub'],
                "refresh_token": str(refresh),
                "access_token": str(access)
            }

            print('res:', res)

            return Response(res, status=status.HTTP_200_OK)
        elif len(user_query) > 1:
            raise ValueError(
                f"There should not be two records with email = {idInfo['email']}.")
        else:
            # There are no users
            print(
                f'user, {idInfo['email']}, is not defined. Creating user, {idInfo['email']}, now')

            user = CustomUser.objects.create_user(
                # ensure only lowercase emails in DB.
                email=idInfo['email'].lower(),
                google_account_linked=True,
                google_sub=idInfo['sub'],
                google_picture_url=idInfo['picture'],
            )

            print('user created:', user)

            print('====Creating access and refresh tokens...====')
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token

            print('refresh: ', refresh)
            print('access: ', access)

            res = {
                "name": idInfo['name'],
                "email": idInfo['email'],
                "picture": idInfo['picture'],
                "google_sub": idInfo['sub'],
                "refresh_token": str(refresh),
                "access_token": str(access)
            }

            print('res:', res)

            return Response(res, status=status.HTTP_200_OK)

    except ValueError as err:
        print('err:', err)


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
