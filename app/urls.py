from django.urls import path, include
from .views import google_sign_in, google_link, google_unlink, apple_sign_in, apple_confirm, apple_link, apple_unlink, email_sign_in, check_email, register, verify_email, login, test_view, send_reset_password_email, reset_password, me, get_node, get_places_tab, set_password, remove_password

app_name = "app"
urlpatterns = [
    # Paths for react-native-google-signin library
    path('google-sign-in', google_sign_in, name="google-sign-in"),
    path('google/link', google_link, name="google-link"),
    path('google/unlink', google_unlink, name="google-unlink"),
    path('apple-sign-in', apple_sign_in, name="apple-sign-in"),
    path('apple/confirm', apple_confirm, name="apple-confirm"),
    path('apple/link', apple_link, name="apple-link"),
    path('apple/unlink', apple_unlink, name="apple-unlink"),
    path('email-sign-in', email_sign_in, name="email-sign-in"),
    path('check-email', check_email, name="check-email"),

    # Paths for user registration
    path('register', register, name="register"),
    path('verify-email/', verify_email, name="verify-email"),

    # Paths for user login
    path('login', login, name="login"),

    path('me', me, name="me"),

    # Test
    path('test-view', test_view, name="test-view"),

    # Paths for reset password
    path('password/set', set_password, name="set-password"),
    path('password/remove', remove_password, name="remove-password"),

    path('send-reset-password-email', send_reset_password_email,
         name="send-reset-password-email"),
    path('reset-password/', reset_password, name='reset-password'),

    # Endpoint for NodeDetail
    path('place-node/<str:node_type>/<int:node_id>', get_node, name="get-node"),

    # Endpoint for Places Tab
    path('places-tab/<int:home_id>', get_places_tab, name='get-places-tab')
]
