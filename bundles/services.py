import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import catalogue_cache, metrics, pricing
from .experiments import assign_variant
from .models import Bundle, BundleItem, Item

logger = logging.getLogger("bundles")


class BundleError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def create_bundle(buyer, item_ids):
    ids = list(dict.fromkeys(item_ids))  # drop duplicates, keep order
    if len(ids) < 2:
        raise BundleError("too_few_items", "A bundle needs at least 2 different items.")

    items = list(Item.objects.filter(id__in=ids))
    if len(items) != len(ids):
        raise BundleError("item_not_found", "One or more items do not exist.", 404)

    if len({item.seller_id for item in items}) != 1:
        raise BundleError("mixed_sellers", "All items must belong to the same seller.")
    seller_id = items[0].seller_id
    if seller_id == buyer.id:
        raise BundleError("own_items", "You cannot bundle your own items.")

    unavailable = sorted(i.id for i in items if i.status != Item.Status.AVAILABLE)
    if unavailable:
        raise BundleError("items_unavailable", f"Items not available: {unavailable}", 409)

    variant = assign_variant(buyer.id)
    price = pricing.calculate([i.price_cents for i in items], variant)

    with transaction.atomic():
        bundle = Bundle.objects.create(
            buyer=buyer,
            seller_id=seller_id,
            variant=variant,
            discount_bps=price.discount_bps,
            subtotal_cents=price.subtotal_cents,
            discount_cents=price.discount_cents,
            total_cents=price.total_cents,
        )
        BundleItem.objects.bulk_create(
            BundleItem(bundle=bundle, item=i, price_cents=i.price_cents) for i in items
        )

    metrics.incr("bundles_created")
    logger.info(
        "bundle_created",
        extra={"data": {"bundle_id": bundle.id, "variant": variant, "total_cents": bundle.total_cents}},
    )
    return bundle


def reserve_bundle(bundle_id):
    """Reserve every item in a bundle, all-or-nothing.

    The guarded UPDATE (`WHERE status = 'available'`) is atomic in the database, so two
    buyers racing for the same item cannot both win. If fewer rows were updated than
    expected, we raise inside the transaction and everything rolls back.
    """
    with transaction.atomic():
        try:
            bundle = Bundle.objects.select_for_update().get(pk=bundle_id)
        except Bundle.DoesNotExist:
            raise BundleError("bundle_not_found", "Bundle not found.", 404) from None

        if bundle.status != Bundle.Status.PENDING:
            raise BundleError("bundle_not_pending", f"Bundle is already {bundle.status}.", 409)

        item_ids = list(bundle.bundle_items.values_list("item_id", flat=True))
        until = timezone.now() + timedelta(minutes=settings.RESERVATION_MINUTES)
        updated = Item.objects.filter(id__in=item_ids, status=Item.Status.AVAILABLE).update(
            status=Item.Status.RESERVED, reserved_until=until
        )
        if updated != len(item_ids):
            metrics.incr("reservations_conflicted")
            raise BundleError("items_unavailable", "Some items were taken by someone else.", 409)

        bundle.status = Bundle.Status.RESERVED
        bundle.reserved_until = until
        bundle.save(update_fields=["status", "reserved_until"])

    catalogue_cache.invalidate(bundle.seller_id)
    metrics.incr("reservations_succeeded")
    logger.info("bundle_reserved", extra={"data": {"bundle_id": bundle.id, "items": len(item_ids)}})
    return bundle


def release_expired_reservations():
    """Give items back to the catalogue when a reservation timed out. Returns the count."""
    now = timezone.now()
    candidate_ids = list(
        Bundle.objects.filter(status=Bundle.Status.RESERVED, reserved_until__lte=now).values_list("id", flat=True)
    )
    released = 0
    for bundle_id in candidate_ids:
        with transaction.atomic():
            bundle = Bundle.objects.select_for_update().get(pk=bundle_id)
            if bundle.status != Bundle.Status.RESERVED:  # changed while we were looping
                continue
            item_ids = bundle.bundle_items.values_list("item_id", flat=True)
            Item.objects.filter(id__in=list(item_ids), status=Item.Status.RESERVED).update(
                status=Item.Status.AVAILABLE, reserved_until=None
            )
            bundle.status = Bundle.Status.EXPIRED
            bundle.save(update_fields=["status"])
        catalogue_cache.invalidate(bundle.seller_id)
        metrics.incr("reservations_released")
        logger.info("reservation_released", extra={"data": {"bundle_id": bundle_id}})
        released += 1
    return released
