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
        alice, created = User.objects.get_or_create(
            email="alice@example.com",
            defaults={"email_verified": True},
        )
        if created:
            alice.set_password("Password123!")
            alice.has_password = True
            alice.save()

        # ---- HOME ----
        apt1 = Home.objects.create(
            name="Alice's Apartment",
            address="123 Main St",
            created_by=alice
        )

        home1 = Home.objects.create(
            name="Alice's Home",
            address="456 Main St",
            created_by=alice
        )

        alice.primary_home = apt1
        alice.save()

        # ---- ROOM ----
        living_room1 = Room.objects.create(
            name="Living Room",
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=apt1,
            created_by=alice
        )

        dining_room1 = Room.objects.create(
            name="Dining Room",
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=apt1,
            created_by=alice
        )

        living_room2 = Room.objects.create(
            name="Living Room",
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=home1,
            created_by=alice
        )

        basement = Room.objects.create(
            name="Basement",
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=home1,
            created_by=alice
        )

        dining_room2 = Room.objects.create(
            name="Dining Room",
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            home=home1,
            created_by=alice
        )

        # --- CONTAINERS ---
        shelf = Container.objects.create(
            name="Shelf",
            room=living_room1,
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            level=1,
            created_by=alice
        )

        box = Container.objects.create(
            name="Box",
            parent_container=shelf,
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            level=shelf.level+1,
            created_by=alice
        )

        small_box = Container.objects.create(
            name="Small Box",
            parent_container=box,
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            level=box.level+1,
            created_by=alice
        )

        ziplock_bag = Container.objects.create(
            name="Ziplock Bag",
            parent_container=small_box,
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            level=small_box.level+1,
            created_by=alice
        )

        envelope = Container.objects.create(
            name="Envelope",
            parent_container=ziplock_bag,
            description="Lorem ipsum dolor sit amet consectetur adipiscing elit quisque faucibus ex sapien vitae pellentesque sem placerat in id cursus mi pretium tellus duis convallis tempus leo eu aenean sed diam urna tempor pulvinar vivamus fringilla lacus nec metus bibendum egestas iaculis massa nisl malesuada lacinia integer nunc posuere ut hendrerit semper vel class aptent taciti sociosqu ad litora torquent per conubia nostra inceptos himenaeos orci varius natoque penatibus et magnis dis parturient montes nascetur ridiculus mus donec rhoncus eros lobortis nulla molestie mattis scelerisque maximus eget fermentum odio phasellus non purus est efficitur laoreet mauris pharetra vestibulum fusce dictum risus.",
            level=ziplock_bag.level+1,
            created_by=alice
        )

        Item.objects.bulk_create([
            # --- LEVEL: SHELF (top-level container) ---
            Item(
                name="Laptop",
                container=shelf,
                category="electronics",
                tags=["work", "expensive"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Router",
                container=shelf,
                category="electronics",
                tags=["network"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Notebook",
                container=shelf,
                category="stationery",
                tags=["work"],
                expiration_date=None,
                created_by=alice
            ),

            # --- LEVEL: BOX (nested under shelf) ---
            Item(
                name="HDMI Cable",
                container=box,
                category="electronics",
                tags=["cable"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Old Phone",
                container=box,
                category="electronics",
                tags=["backup", "old"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Batteries",
                container=box,
                category="household",
                tags=["AA"],
                expiration_date=None,
                created_by=alice
            ),

            # --- LEVEL: SMALL BOX (deep nesting) ---
            Item(
                name="USB Drive",
                container=small_box,
                category="electronics",
                tags=["storage"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="SD Card",
                container=small_box,
                category="electronics",
                tags=["camera"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Old Receipts",
                container=small_box,
                category="documents",
                tags=["paper", "old"],
                expiration_date=None,
                created_by=alice
            ),

            # --- EDGE CASES (this is where most people are too weak) ---

            # duplicate names in SAME container
            Item(
                name="Box Cutter",
                container=shelf,
                category="tools",
                tags=[],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Box Cutter",
                container=shelf,
                category="tools",
                tags=["sharp"],
                expiration_date=None,
                created_by=alice
            ),

            # same item name across DIFFERENT levels
            Item(
                name="Charger",
                container=shelf,
                category="electronics",
                tags=["phone"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Charger",
                container=box,
                category="electronics",
                tags=["laptop"],
                expiration_date=None,
                created_by=alice
            ),

            # long name (UI overflow test)
            Item(
                name="Very Long Item Name That Should Definitely Overflow Or Wrap In The UI To Test Layout Behavior",
                container=small_box,
                category="test",
                tags=["ui"],
                expiration_date=None,
                created_by=alice
            ),

            # empty tags
            Item(
                name="Mystery Item",
                container=box,
                category="unknown",
                tags=[],
                expiration_date=None,
                created_by=alice
            ),
            # --- LEVEL 4: ZIPLOCK BAG ---
            Item(
                name="Rubber Bands",
                container=ziplock_bag,
                category="office",
                tags=["small"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Paper Clips",
                container=ziplock_bag,
                category="office",
                tags=["metal"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Coins",
                container=ziplock_bag,
                category="misc",
                tags=["loose"],
                expiration_date=None,
                created_by=alice
            ),

            # --- LEVEL 5: ENVELOPE (DEEPEST LEVEL) ---
            Item(
                name="Passport",
                container=envelope,
                category="documents",
                tags=["important"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Birth Certificate",
                container=envelope,
                category="documents",
                tags=["important"],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Cash",
                container=envelope,
                category="money",
                tags=["hidden"],
                expiration_date=None,
                created_by=alice
            ),

            # --- EDGE CASES AT MAX DEPTH ---

            # duplicate names at deepest level
            Item(
                name="Key",
                container=envelope,
                category="misc",
                tags=[],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Key",
                container=envelope,
                category="misc",
                tags=["spare"],
                expiration_date=None,
                created_by=alice
            ),

            # same item name across multiple depths
            Item(
                name="Documents",
                container=box,
                category="documents",
                tags=[],
                expiration_date=None,
                created_by=alice
            ),
            Item(
                name="Documents",
                container=envelope,
                category="documents",
                tags=["critical"],
                expiration_date=None,
                created_by=alice
            ),

            # long + messy naming (real user behavior)
            Item(
                name="Very Important Documents Do Not Throw Away Under Any Circumstances",
                container=envelope,
                category="documents",
                tags=["urgent", "important"],
                expiration_date=None,
                created_by=alice
            ),

            # empty + ambiguous
            Item(
                name="Stuff",
                container=ziplock_bag,
                category="unknown",
                tags=[],
                expiration_date=None,
                created_by=alice
            ),
        ])

        # ---- MEMBERSHIPS ----
        HomeMembership.objects.bulk_create([
            HomeMembership(user=alice, home=apt1),
            HomeMembership(user=alice, home=home1),
        ])

        self.stdout.write(self.style.SUCCESS(
            "Dummy data created successfully!"))
