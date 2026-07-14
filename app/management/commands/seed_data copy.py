from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from app.models import Home, Room, Container, Item, HomeMembership
from django.utils import timezone
import random

User = get_user_model()


class Command(BaseCommand):
    help = "Seed database with dummy data"

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding data...")

        # ---- USERS ----
        # These test users were already created in db.
        user1 = User.objects.get(email="alice@example.com")
        user2 = User.objects.get(email="bob@example.com")
        user3 = User.objects.get(email="charlie@example.com")

        # ---- HOME ----
        apt1 = Home.objects.create(
            name="Alice's Apartment",
            address="123 Main St",
            created_by=user1
        )

        home1 = Home.objects.create(
            name="Alice's House",
            address="456 Main St",
            created_by=user1
        )

        apt2 = Home.objects.create(
            name="Bob's Apartment",
            address="123 Utopia Pkwy",
            created_by=user2
        )

        #
        home2 = Home.objects.create(
            name="Bob's House",
            address="456 Utopia Pkwy",
            created_by=user2
        )

        apt3 = Home.objects.create(
            name="Charlie's Apartment",
            address="123 Kissena Blvd",
            created_by=user3
        )

        home3 = Home.objects.create(
            name="Charlie's House",
            address="456 Kissena Blvd",
            created_by=user3
        )

        # ---- MEMBERSHIPS ----
        HomeMembership.objects.bulk_create([
            HomeMembership(user=user1, home=apt1),
            HomeMembership(user=user1, home=home1),
            HomeMembership(user=user2, home=apt2),
            HomeMembership(user=user2, home=home2),
            HomeMembership(user=user3, home=apt3),
            HomeMembership(user=user3, home=home3),
            HomeMembership(user=user3, home=home1),
        ])

        # HomeMembership.objects.bulk_create([
        #     HomeMembership(user=user1, home=home1),
        #     HomeMembership(user=user2, home=home1),
        # ])

        self.stdout.write(self.style.SUCCESS(
            "Dummy data created successfully!"))

    def populate_user_apartment_data(self, user, apartment):
        """
        Populate a user's apartment with sample rooms, nested containers, and items.
        """
        username = user.email.split['@'][0]

        living_room = Room.objects.create(
            name="Living Room",
            description=f"{user}'s main chill area in her apartment. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=apartment,
            created_by=user
        )

        dining_room = Room.objects.create(
            name="Dining Room",
            description=f"{username}'s eating area in her apartment. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=apartment,
            created_by=user
        )

        kitchen_apt = Room.objects.create(
            name="Kitchen",
            description=f"{username}'s cooking area in her apartment. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=apartment,
            created_by=user
        )

        bedroom = Room.objects.create(
            name="Bedroom",
            description=f"{username}'s sleeping area in her apartment. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=apartment,
            created_by=user
        )

        # --- CONTAINERS ---
        shelf_living_room = Container.objects.create(
            name="Shelf",
            room=living_room,
            description="Shelf in Alice's Living Room. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            level=1,
            created_by=user
        )

        box_shelf_living_room = Container.objects.create(
            name="Box",
            description="Box on shelf in alice's apartment's living room. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            parent_container=shelf_living_room,
            level=2,
            created_by=user
        )

        small_box_box_shelf_living_room = Container.objects.create(
            name="Small Box",
            description="Small box inside Box. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            parent_container=box_shelf_living_room,
            level=3,
            created_by=user
        )

        shelf_dining_room = Container.objects.create(
            name="Shelf",
            description="Shelf in dining room in Alice's apartment's dining room. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            room=dining_room,
            parent_container=None,
            level=1,
            created_by=user
        )

        # ---- ITEMS ----
        Item.objects.bulk_create([
            Item(
                name="Laptop",
                container=shelf_living_room,
                category="electronics",
                tags=["work", "expensive"],
                expiration_date=None,
                created_by=user
            ),
            Item(
                name="Screwdriver",
                container=box_shelf_living_room,
                category="tools",
                tags=["repair"],
                created_by=user
            ),
            Item(
                name="Passport",
                container=small_box_box_shelf_living_room,
                category="documents",
                tags=["important"],
                created_by=user
            ),
            Item(
                name="T-shirt",
                room=bedroom,
                category="clothing",
                tags=["casual"],
                created_by=user
            ),
            Item(
                name="Milk",
                room=kitchen_apt,
                category="kitchen",
                expiration_date=timezone.now().date(),
                created_by=user
            ),
            Item(
                name="Mahjong Set",
                room=None,
                container=shelf_dining_room,
                tags=["games"],
                created_by=user
            ),
            Item(
                name="Chess Board",
                room=None,
                container=box_shelf_living_room,
                tags=["games"],
                created_by=user
            ),
        ])

    def populate_user_house_data(self, user, house):
        """
        Populate a user's house with sample rooms, nested containers, and items.        
        """
        username = user.email.split['@'][0]

        living_room = Room.objects.create(
            name="Living Room",
            description=f"{username}'s main chill area in her home. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=house,
            created_by=user
        )

        dining_room = Room.objects.create(
            name="Dining Room",
            description=f"{username}'s eating area in her home. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=house,
            created_by=user
        )

        kitchen = Room.objects.create(
            name="Kitchen",
            description=f"{username}'s cooking area in her home. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=house,
            created_by=user
        )

        basement = Room.objects.create(
            name="Basement",
            description=f"{username}'s basement area in her home. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=house,
            created_by=user
        )

        # ---- CONTAINERS (nested) ----
        shelf_living_room = Container.objects.create(
            name="Shelf",
            room=living_room,
            description=f"Shelf in {username}'s home's Living Room. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            level=1,
            created_by=user
        )

        box_shelf_living_room = Container.objects.create(
            name="Box",
            description=f"Box on shelf in {username}'s home's living room. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            parent_container=shelf_living_room,
            level=2,
            created_by=user
        )

        small_box_box_shelf_living_room = Container.objects.create(
            name="Small Box",
            description=f"Small box inside Box. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            parent_container=box_shelf_living_room,
            level=3,
            created_by=user
        )

        shelf_dining_room = Container.objects.create(
            name="Shelf",
            description=f"Shelf in dining room in {username}'s home's dining room. Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            room=dining_room,
            parent_container=None,
            level=1,
            created_by=user
        )

        # ---- ITEMS ----
        Item.objects.bulk_create([
            Item(
                name="Laptop",
                container=shelf_living_room,
                category="electronics",
                tags=["work", "expensive"],
                expiration_date=None,
                created_by=user
            ),
            Item(
                name="Screwdriver",
                container=box_shelf_living_room,
                category="tools",
                tags=["repair"],
                created_by=user
            ),
            Item(
                name="Passport",
                container=small_box_box_shelf_living_room,
                category="documents",
                tags=["important"],
                created_by=user
            ),
            Item(
                name="T-shirt",
                room=bedroom,
                category="clothing",
                tags=["casual"],
                created_by=user
            ),
            Item(
                name="Milk",
                room=kitchen,
                category="kitchen",
                expiration_date=timezone.now().date(),
                created_by=user
            ),
            Item(
                name="Mahjong Set",
                room=None,
                container=shelf_dining_room,
                tags=["games"],
                created_by=user
            ),
            Item(
                name="Chess Board",
                room=None,
                container=box_shelf_living_room,
                tags=["games"],
                created_by=user
            ),
        ])
