from django.core.cache import cache

from bundles.experiments import assign_variant
from bundles.models import Item, Member


def reset_cache():
    cache.clear()


def make_seller_with_items(username="seller", prices=(1000, 2000, 3000)):
    seller = Member.objects.create(username=username)
    items = [Item.objects.create(seller=seller, title=f"Item {p}", price_cents=p) for p in prices]
    return seller, items


def make_buyer(username="buyer", variant=None):
    """Create a buyer; optionally keep creating until the user lands in the wanted variant."""
    buyer = Member.objects.create(username=username)
    while variant and assign_variant(buyer.id) != variant:
        buyer = Member.objects.create(username=f"{username}-{Member.objects.count()}")
    return buyer
