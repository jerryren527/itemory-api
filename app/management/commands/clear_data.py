from django.core.management.base import BaseCommand
from app.models import Home, Room, Container, Item, HomeMembership
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Clear all dummy data"

    def handle(self, *args, **kwargs):
        self.stdout.write("Deleting all data...")

        Item.objects.all().delete()
        Container.objects.all().delete()
        Room.objects.all().delete()
        HomeMembership.objects.all().delete()
        Home.objects.all().delete()

        # Optional: delete test users
        User.objects.filter(email__in=[
            "alice@example.com",
        ]).delete()

        self.stdout.write(self.style.SUCCESS("All dummy data deleted."))
