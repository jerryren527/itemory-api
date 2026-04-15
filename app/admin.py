from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, PasswordResetToken, Home, Room, Container, Item, HomeMembership
from .forms import CustomUserChangeForm, CustomUserCreationForm

# Register your models here.


class CustomUserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ("email", "is_staff", "is_superuser",
                    "google_account_linked", "has_password", "email_verified")
    list_filter = ("is_staff", "is_superuser", "google_account_linked")

    fieldsets = (
        (None, {"fields": ("email", "password", "primary_home")}),
        ("Authentication", {"fields": (
            "has_password", "google_account_linked", "google_sub", "google_picture_url")}),
        ("Permissions", {"fields": ("is_staff",
         "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": (
            "last_login", "date_joined", "email_verified", "email_verified_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    search_fields = ("email", "google_sub")
    ordering = ("email",)


@admin.register(Home)
class HomeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'address', 'created_by',
                    'created_at', 'updated_at')
    search_fields = ('name', 'address', 'created_by__email')
    list_filter = ('created_at',)
    ordering = ('-created_at',)


@admin.register(HomeMembership)
class HomeMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'home')
    search_fields = ('user__email', 'home__name')
    list_filter = ('home', 'user')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'home', 'created_by',
                    'created_at', 'updated_at')
    search_fields = ('name', 'description', 'home__name', 'created_by__email')
    list_filter = ('home', 'created_at',)


@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'room', 'parent_container',
                    'level', 'created_by', 'created_at', 'updated_at')
    search_fields = ('name', 'description', 'room__name',
                     'parent_container__name', 'created_by__email')
    list_filter = ('room', 'level', 'created_at',)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'room', 'container',
                    'category', 'expiration_date', 'created_at')
    search_fields = ('name', 'comment', 'tags', 'room__name',
                     'container__name', 'created_by__email')
    list_filter = ('room', 'container', 'category',
                   'expiration_date', 'created_at')


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(PasswordResetToken)
