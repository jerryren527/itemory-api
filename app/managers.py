from django.contrib.auth.base_user import BaseUserManager
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """
        Internal helper method used by create_user() and create_superuser().
        """

        if not email:
            raise ValueError("An email address is required.")

        # AbstractBaseUser.normalize_email() lowercases the domain part of it. Also lowercase the username-part of email address so that DB only contains lowercase emails.
        email = self.normalize_email(email).lower()

        # Create a new CustomUser model instance with initial fields without immedidately saving it to the database.
        user = self.model(email=email, **extra_fields)

        # Modify the model instance before saving it to the database.
        if password:
            user.set_password(password)  # AbstractBaseUser.set_password()
            user.has_password = True  # AbstractBaseUser.set_password()
            # user.has_usable_password = True
        else:
            # No password provided → Google-only or future password creation
            user.has_password = False
            # user.has_usable_password = False

        if not user.date_joined:
            user.date_joined = timezone.now()

        # Saves the user to the whatever database this manager is currently operating on. Only one database is used for this project (named 'default'), so this line operates the same as 'user.save()'. Keep '.save(using=self._db)' to future-proof this project in case multiple databases are used.
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and return a regular user.

        extra_fields: dict of all additional keyword arguments.
        """
        # dict.setdefault(key, default_value) is a Python dictionary method. If the key is not in the dict, set it to default_value. If it is already in the dict, do nothing.
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("google_account_linked", extra_fields.get(
            "google_account_linked", False))

        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and return a superuser.
        """

        if not password:
            raise ValueError("Superusers must have a password.")

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("has_password", True)

        # Sanity checks
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)
