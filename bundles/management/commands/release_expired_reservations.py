from django.core.management.base import BaseCommand

from bundles.services import release_expired_reservations


class Command(BaseCommand):
    help = "Release items whose 15 minute reservation has expired."

    def handle(self, *args, **options):
        count = release_expired_reservations()
        self.stdout.write(f"Released {count} expired reservation(s).")
