from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from .managers import CustomUserManager

# Create your models here.


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)

    # Authentication
    has_password = models.BooleanField(default=False)
    google_account_linked = models.BooleanField(default=False)
    google_sub = models.CharField(max_length=255, null=True, blank=True)
    google_picture_url = models.URLField(null=True, blank=True)
    apple_account_linked = models.BooleanField(default=False)
    apple_sub = models.CharField(max_length=255, null=True, blank=True, unique=True)

    # Required fields needed for CustomUser to work with Django Admin. Extending AbstractUser will provide fields like is_active, is_staff, is_superuser, date_joined. But CustomUser extends AbstractBaseUser. So I NEED to provide these fields myself. Django expects them for Django admin, and createsuperuser. The minimum required fields are is_staff and is_active.
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    # Email verification
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(blank=True, null=True)

    # Required by Django
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    # Primary home logic
    primary_home = models.ForeignKey('Home', on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name='primary_for_users')

    def __str__(self):
        return self.email

    objects = CustomUserManager()


class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    # null=True the db allows NULL. blank=True means Dnango forms allow empty field during validation.
    used_at = models.DateField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.token


class Home(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True, null=True)
    # on_delete=models.SET_NULL sets the field to NULL when the parent object is deleted.
    # To access all objected created by a particlar CustomUser, use Django's auto-generated name, like customuser.home_set.all(). If you want a more descriptive name, define related_name, like related_name='homes_created'.
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # set the field to now every time the object is saved
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"({self.id}): {self.name}"


class HomeMembership(models.Model):
    # If you delete a user, then the membership should disappear because a membership without a user has no meaning.
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="memberships")
    # If you delete a home, then the membership should disappear because a membership without a home has no meaning.
    home = models.ForeignKey(Home, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'home')

    def __str__(self):
        return f"{self.user.email} - {self.home.name}"


class Room(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=1000, blank=True, null=True)
    home = models.ForeignKey(Home, on_delete=models.CASCADE)
    picture = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"({self.id}): {self.name}"


class Container(models.Model):
    LEVEL_CHOICES = [(i, f"Level {i}") for i in range(1, 6)]

    name = models.CharField(max_length=255)
    description = models.TextField(max_length=1000, blank=True, null=True)
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, null=True, blank=True)
    parent_container = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True)
    level = models.IntegerField(choices=LEVEL_CHOICES, validators=[
                                MinValueValidator(1), MaxValueValidator(5)])
    # URLField is a CharField for a URL, validated by URLValidator.
    picture = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"({self.id}): {self.name}"

    def clean(self):
        if self.room and self.parent_container:
            raise ValidationError("Container cannot belong to both room and parent container.")

        if not self.room and not self.parent_container:
            raise ValidationError("Container must belong to either a room or parent container.")

    def save(self, *args, **kwargs):
        """
        container.save() does not automatically call clean(). So override container.save()
        - About full_clean method: https://docs.djangoproject.com/en/6.0/ref/models/instances/#validating-objects
        """
        self.full_clean()
        super().save(*args, **kwargs)


class Item(models.Model):
    CATEGORY_CHOICES = [
        ('electronics', 'Electronics'),
        ('tools', 'Tools'),
        ('documents', 'Documents'),
        ('clothing', 'Clothing'),
        ('kitchen', 'Kitchen'),
    ]

    STATUS_CHOICES = [
        ('in_use', 'In-Use'),
        ('stored', 'Stored')
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(max_length=1000, blank=True, null=True)
    room = models.ForeignKey(
        # If the room is deleted, then Item.room is set to Null.
        Room, on_delete=models.SET_NULL, null=True, blank=True)
    container = models.ForeignKey(
        # If the container is deleted, then Item.container is set to Null.
        Container, on_delete=models.SET_NULL, null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=50), blank=True, null=True)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, blank=True, null=True)
    expiration_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="stored")
    quantity = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True)
    # pictures = ArrayField(models.URLField(), blank=True, null=True)
    picture = models.URLField(blank=True, null=True)
    comment = models.TextField(max_length=1000, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"({self.id}): {self.name}"

    def clean(self):
        if self.container and self.room:
            raise ValidationError("Item cannot belong to both container and room.")

        if not self.container and not self.room:
            raise ValidationError("Item must belong to either a container or a room")

    def save(self, *args, **kwargs):
        """
        item.save() does not automatically call clean(). So override item.save()
        - About full_clean method: https://docs.djangoproject.com/en/6.0/ref/models/instances/#validating-objects
        """
        self.full_clean()
        super().save(*args, **kwargs)
