from django.urls import path, include
from .views import google_sign_in, google_link, google_unlink, apple_sign_in, apple_confirm, apple_link, apple_unlink, email_sign_in, check_email, register, verify_email, login, test_view, send_reset_password_email, reset_password, me, get_node, get_homes, set_password, remove_password, update_username, create_home, set_primary_home, search_nodes, rename_home, update_home_address, delete_home, share_home, get_home_members, remove_home_member, create_room, create_container, create_item, rename_node, delete_node, update_item, checkout_item, return_item_checkout, checked_out_items, star_node, unstar_node, starred_nodes

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
    path('username', update_username, name="update-username"),

    path('send-reset-password-email', send_reset_password_email,
         name="send-reset-password-email"),
    path('reset-password/', reset_password, name='reset-password'),

    # Endpoint for NodeDetail
    path('place-node/<str:node_type>/<int:node_id>', get_node, name="get-node"),
    path('place-node/<str:node_type>/<int:node_id>/rename', rename_node, name="rename-node"),
    path('place-node/<str:node_type>/<int:node_id>/delete', delete_node, name="delete-node"),
    path('place-node/<str:node_type>/<int:node_id>/star', star_node, name="star-node"),
    path('place-node/<str:node_type>/<int:node_id>/unstar', unstar_node, name="unstar-node"),

    # Endpoint for the Homes list
    path('homes', get_homes, name='get-homes'),

    # Endpoint for Search
    path('search', search_nodes, name='search-nodes'),

    # Endpoints for Home creation and primary home selection
    path('create-home', create_home, name='create-home'),
    path('set-primary-home', set_primary_home, name='set-primary-home'),

    # Endpoints for Home management (creator-only)
    path('home/<int:home_id>/rename', rename_home, name='rename-home'),
    path('home/<int:home_id>/address', update_home_address, name='update-home-address'),
    path('home/<int:home_id>/delete', delete_home, name='delete-home'),
    path('home/<int:home_id>/share', share_home, name='share-home'),
    path('home/<int:home_id>/members', get_home_members, name='get-home-members'),
    path('home/<int:home_id>/remove-member', remove_home_member, name='remove-home-member'),

    # Endpoints for creating Rooms/Containers/Items
    path('room', create_room, name='create-room'),
    path('container', create_container, name='create-container'),
    path('item', create_item, name='create-item'),
    path('item/<int:item_id>/update', update_item, name='update-item'),
    path('item/<int:item_id>/checkout', checkout_item, name='checkout-item'),
    path('item/<int:item_id>/return', return_item_checkout, name='return-item-checkout'),
    path('checked-out-items', checked_out_items, name='checked-out-items'),
    path('starred-nodes', starred_nodes, name='starred-nodes'),
]
