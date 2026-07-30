from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.mail import send_mail
from rest_framework.exceptions import AuthenticationFailed
from django.core.signing import TimestampSigner
from .models import CustomUser, Room, Container, Item, HomeMembership, Home
from .services.search_helpers import get_home_id_for_item


User = get_user_model()  # reads AUTH_USER_MODEL in settings.py


class IdentifySerializer(serializers.Serializer):
    # serializers.Serializer class gives you access to is_valid() and .errors property
    # EmailField has a EmailValidator class throws a ValidationError if the email string is not formatted correctly.
    email = serializers.EmailField()

    def get_user_by_email(self, email):
        """
        If the email is found in the database, return the first CustomUser instance with that email. Else return None.

        :param email: email address
        """
        # Gets the first CustomUser instance with this email. Use Django ORM's case-insensitive lookups with i prefix. 'iexact' is a case-insensitive exact match.
        user = CustomUser.objects.filter(email__iexact=email).first()
        if user:
            return user
        else:
            return None


class LoginSerializer(serializers.Serializer):
    # serializers.Serializer class gives you access to is_valid() and .errors property
    # 'identifier' accepts either an email address or a username; resolved to a user in the view.
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """
        Called after 'email' and 'password' fields are validated.

        :param attrs: a passed in dictionary of attributes.
        """
        # email = attrs['email'].lower()  # lowercase the user's input
        # password = attrs['password']

        # # Should I separate out the authenticate() logic to the view?
        # # django.contrib.auth.authenticate is case-sensitive, that is why we lowercased email.
        # user = authenticate(
        #     request=self.context.get('request'),
        #     email=email,
        #     password=password
        # )

        # print('user', user)

        # if not user:
        #     raise serializers.ValidationError("Invalid email or password.")

        # # Attached user for view to access
        # attrs['user'] = user
        return attrs


class RegisterSerializer(serializers.Serializer):
    # serializers.Serializer class gives you access to is_valid() and .errors property

    # Declare a serializer is similar to declaring a form. Access the serializer's properties with `.data` property on a RegisterSerializer instnace.
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(max_length=30)

    def validate_password(self, value):
        # django's validate_password() returns None if password is valid. Raises ValidationError
        validate_password(value)
        return value

    def validate_username(self, value):
        if CustomUser.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def create(self, validated_data):
        return CustomUser.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            username=validated_data["username"],
        )

    def send_verification_email(self, user):
        # print('===INSIDE send_verification_email()===')
        # print(user)

        token = signing.dumps({"user_id": user.id})
        # The verification url is just a normal HTTP GET link with a token passed as a query parameter. This url is emailed to the email address.
        verification_url = f"http://127.0.0.1:8000/app/verify-email/?token={token}"
        # Trying with Scheme. I change my mind. To support cross-platform, I will keep the verification url as a web-based URL. I also still have not figured out how to make the deep link work.
        # verification_url = f"itemory://VerifyEmailPage/?token={token}"

        send_mail(
            subject="Verify your email address",
            message=f"Click here to verify: {verification_url}",
            from_email="itemoryapp@gmail.com",
            recipient_list=[user.email],
            fail_silently=False,  # Will raise smtplib.SMTPException if an error occurs
        )


class ResetPasswordSerializer(serializers.Serializer):
    # serializers.Serializer class gives you access to is_valid() and .errors property

    # Declare a serializer is similar to declaring a form. Access the serializer's properties with `.data` property on a RegisterSerializer instnace.
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        # django's validate_password() returns None if password is valid (according to configured rules defined in settings.py's AUTH_PASSWORD_VALIDATORS). Raises ValidationError
        # serializer.validate_password() is automatically called during serializer.is_valid()
        # Context (e.g.., { 'user': 'user_email_address@email.com' } ) is passed into the ResetPasswordSerializer. It can be accessed in the optional 'user' argument.
        # validate_password() takes optional 'user' argument, which can be used to compare it to the user (auth rule: django.contrib.auth.password_validation.UserAttributeSimilarityValidator).
        validate_password(value, user=self.context.get('user'))
        return value

    def validate(self, attrs):
        """
        Runs full object-level validation. Checks if password and confirm_password match.
        https://www.django-rest-framework.org/api-guide/serializers/#object-level-validation
        - serializer.validate() is automatically called during serializer.is_valid() (after validate_password() is called.)
        """
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."})

        return attrs

    def update(self, validated_data):
        pass


class SetPasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        validate_password(value, user=self.context.get('user'))
        return value

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        user = self.context.get('user')
        if user is not None and user.has_password:
            old_password = attrs.get('old_password')
            if not old_password:
                raise serializers.ValidationError({"old_password": "Old password is required."})
            if not user.check_password(old_password):
                raise serializers.ValidationError({"old_password": "Old password is incorrect."})

        return attrs


# class NameSerializer(serializers.Serializer):
#     name = serializers.CharField()

class NodeDetailsSerializer(serializers.Serializer):
    """
    Shared by Room and Container node details. `level` is only meaningful
    for Container (1-5); Room has no such attribute, so it serializes as null.
    """
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    picture = serializers.URLField(allow_null=True)
    level = serializers.SerializerMethodField()
    is_starred = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField()

    def get_level(self, obj):
        return getattr(obj, 'level', None)

    def get_is_starred(self, obj):
        return self.context.get('is_starred', False)


class ChildSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    expiration_date = serializers.SerializerMethodField()
    is_starred = serializers.SerializerMethodField()

    def get_type(self, obj):
        if isinstance(obj, Room):
            return "room"
        elif isinstance(obj, Container):
            return "container"
        elif isinstance(obj, Item):
            return "item"

    def get_thumbnail(self, obj):
        return obj.picture

    def get_quantity(self, obj):
        node_type = self.get_type(obj)
        if node_type == 'item':
            return obj.quantity
        return None

    def get_expiration_date(self, obj):
        node_type = self.get_type(obj)
        if node_type == 'item':
            return obj.expiration_date
        return None

    def get_is_starred(self, obj):
        """
        starred_keys (a set of (type, id) tuples for the requesting user) is
        passed via context by the view - see get_starred_keys in views.py.
        """
        starred_keys = self.context.get('starred_keys') or set()
        return (self.get_type(obj), obj.id) in starred_keys


class SearchResultSerializer(ChildSerializer):
    """
    A search result is a room/container/item, tagged with the home it was
    found in. home_id/home_name are attached as ad hoc attributes on the raw
    model instance by the search view before serializing (see search_nodes).
    """
    home_id = serializers.IntegerField()
    home_name = serializers.CharField()


class CheckedOutItemSerializer(SearchResultSerializer):
    """
    An item the requesting user has checked out, tagged with the home it
    lives in (see SearchResultSerializer) plus the quantity *this user* has
    checked out (checked_out_quantity is attached as an ad hoc attribute on
    the raw Item instance before serializing - see checked_out_items).
    """

    def get_quantity(self, obj):
        return obj.checked_out_quantity


class StarredNodeSerializer(SearchResultSerializer):
    """
    A room/container/item the requesting user has starred, tagged with the
    home it lives in (home_id/home_name attached as ad hoc attributes on the
    raw model instance before serializing - see starred_nodes) plus
    updated_at, a genuine field on Room/Container/Item.
    """
    updated_at = serializers.DateTimeField()

    def get_is_starred(self, obj):
        # Every node in this list is starred by definition - no need to
        # look up starred_keys (not passed via context here).
        return True


class ItemNodeDetailsSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    picture = serializers.URLField(allow_null=True)
    quantity = serializers.IntegerField()
    expiration_date = serializers.DateField(allow_null=True)
    category = serializers.CharField(allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(), allow_null=True)
    comment = serializers.CharField(allow_null=True)
    available_quantity = serializers.SerializerMethodField()
    checkouts = serializers.SerializerMethodField()
    can_manage_checkouts = serializers.SerializerMethodField()
    is_starred = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField()

    def get_is_starred(self, obj):
        return self.context.get('is_starred', False)

    def get_available_quantity(self, obj):
        checked_out = sum(c.quantity for c in obj.checkouts.all())
        return max(obj.quantity - checked_out, 0)

    def get_checkouts(self, obj):
        return [
            {"user_id": c.user_id, "username": c.user.username, "quantity": c.quantity}
            for c in obj.checkouts.select_related('user').order_by('user__username')
        ]

    def get_can_manage_checkouts(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        home_id = get_home_id_for_item(obj)
        home = Home.objects.filter(pk=home_id).first() if home_id else None
        return bool(home and home.created_by_id == request.user.id)


class HomeSerializer(serializers.Serializer):
    """
    Serializer used to display a Home: in the Homes list, as a drill-down
    node (node_type='home'), and after mutating actions (rename/share/etc).
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField(allow_null=True)
    updated_at = serializers.DateTimeField()
    is_primary = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()
    is_creator = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()

    def get_is_primary(self, obj):
        """
        HomeSerializer(some_home, context={'user': request.user})
        - calls get_is_primary(self, obj), where obj is some_home.
        - obj is the object being serialzed - some_home, a Home instance.
        """
        user = self.context['user']  # from context parameter passed into the serializer
        return user.primary_home == obj

    def get_is_shared(self, obj):
        return HomeMembership.objects.filter(home=obj).count() > 1

    def get_is_creator(self, obj):
        user = self.context['user']
        return obj.created_by_id == user.id

    def get_owner_username(self, obj):
        # created_by is SET_NULL if the creator's account was later deleted.
        return obj.created_by.username if obj.created_by else None
