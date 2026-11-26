from django.core.management.base import BaseCommand

from bundles.models import Item, Member

DEMO_ITEMS = [
    ("Denim jacket", 2500),
    ("Wool scarf", 1200),
    ("Leather boots", 4500),
    ("Band t-shirt", 800),
    ("Vintage jeans", 3000),
]


class Command(BaseCommand):
    help = "Create demo users and items (safe to run repeatedly)."

    def handle(self, *args, **options):
        seller, created = Member.objects.get_or_create(username="seller")
        Member.objects.get_or_create(username="buyer")
        if created:
            Item.objects.bulk_create(Item(seller=seller, title=t, price_cents=p) for t, p in DEMO_ITEMS)
        self.stdout.write("Demo data ready: seller id=1, buyer id=2, items 1-5.")
