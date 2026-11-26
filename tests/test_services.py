from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from bundles import services
from bundles.models import Bundle, Item
from bundles.services import BundleError

from .helpers import make_buyer, make_seller_with_items, reset_cache


class CreateBundleTests(TestCase):
    def setUp(self):
        reset_cache()
        self.seller, self.items = make_seller_with_items()
        self.buyer = make_buyer(variant="A")

    def test_creates_bundle_with_discount(self):
        bundle = services.create_bundle(self.buyer, [i.id for i in self.items])
        self.assertEqual(bundle.subtotal_cents, 6000)
        self.assertEqual(bundle.discount_cents, 600)  # variant A, 3 items = 10%
        self.assertEqual(bundle.total_cents, 5400)
        self.assertEqual(bundle.status, Bundle.Status.PENDING)

    def test_duplicate_ids_are_collapsed(self):
        with self.assertRaises(BundleError) as ctx:
            services.create_bundle(self.buyer, [self.items[0].id, self.items[0].id])
        self.assertEqual(ctx.exception.code, "too_few_items")

    def test_single_item_is_rejected(self):
        with self.assertRaises(BundleError) as ctx:
            services.create_bundle(self.buyer, [self.items[0].id])
        self.assertEqual(ctx.exception.code, "too_few_items")

    def test_mixed_sellers_are_rejected(self):
        _, other_items = make_seller_with_items("other", (500,))
        with self.assertRaises(BundleError) as ctx:
            services.create_bundle(self.buyer, [self.items[0].id, other_items[0].id])
        self.assertEqual(ctx.exception.code, "mixed_sellers")

    def test_unknown_item_is_rejected(self):
        with self.assertRaises(BundleError) as ctx:
            services.create_bundle(self.buyer, [self.items[0].id, 99999])
        self.assertEqual(ctx.exception.code, "item_not_found")

    def test_sold_or_reserved_items_cannot_be_bundled(self):
        for status in (Item.Status.SOLD, Item.Status.RESERVED):
            Item.objects.filter(pk=self.items[0].id).update(status=status)
            with self.assertRaises(BundleError) as ctx:
                services.create_bundle(self.buyer, [self.items[0].id, self.items[1].id])
            self.assertEqual(ctx.exception.code, "items_unavailable")

    def test_seller_cannot_buy_own_items(self):
        with self.assertRaises(BundleError) as ctx:
            services.create_bundle(self.seller, [self.items[0].id, self.items[1].id])
        self.assertEqual(ctx.exception.code, "own_items")


class ReserveBundleTests(TestCase):
    def setUp(self):
        reset_cache()
        self.seller, self.items = make_seller_with_items()
        self.buyer = make_buyer("buyer1")
        self.other_buyer = make_buyer("buyer2")

    def test_reserve_marks_items_and_sets_expiry(self):
        bundle = services.create_bundle(self.buyer, [self.items[0].id, self.items[1].id])
        services.reserve_bundle(bundle.id)
        bundle.refresh_from_db()
        self.assertEqual(bundle.status, Bundle.Status.RESERVED)
        self.assertEqual(Item.objects.filter(status=Item.Status.RESERVED).count(), 2)
        self.assertGreater(bundle.reserved_until, timezone.now() + timedelta(minutes=14))

    def test_second_buyer_cannot_reserve_overlapping_items(self):
        first = services.create_bundle(self.buyer, [self.items[0].id, self.items[1].id])
        second = services.create_bundle(self.other_buyer, [self.items[1].id, self.items[2].id])
        services.reserve_bundle(first.id)

        with self.assertRaises(BundleError) as ctx:
            services.reserve_bundle(second.id)
        self.assertEqual(ctx.exception.status, 409)

        # All-or-nothing: the free item (items[2]) must NOT have been reserved by the failed attempt.
        self.items[2].refresh_from_db()
        self.assertEqual(self.items[2].status, Item.Status.AVAILABLE)
        second.refresh_from_db()
        self.assertEqual(second.status, Bundle.Status.PENDING)

    def test_cannot_reserve_twice(self):
        bundle = services.create_bundle(self.buyer, [self.items[0].id, self.items[1].id])
        services.reserve_bundle(bundle.id)
        with self.assertRaises(BundleError) as ctx:
            services.reserve_bundle(bundle.id)
        self.assertEqual(ctx.exception.code, "bundle_not_pending")

    def test_unknown_bundle(self):
        with self.assertRaises(BundleError) as ctx:
            services.reserve_bundle(12345)
        self.assertEqual(ctx.exception.status, 404)


class ReleaseExpiredTests(TestCase):
    def setUp(self):
        reset_cache()
        self.seller, self.items = make_seller_with_items()
        self.buyer = make_buyer()

    def test_expired_reservation_is_released(self):
        bundle = services.create_bundle(self.buyer, [self.items[0].id, self.items[1].id])
        services.reserve_bundle(bundle.id)
        Bundle.objects.filter(pk=bundle.id).update(reserved_until=timezone.now() - timedelta(minutes=1))

        self.assertEqual(services.release_expired_reservations(), 1)

        bundle.refresh_from_db()
        self.assertEqual(bundle.status, Bundle.Status.EXPIRED)
        self.assertEqual(Item.objects.filter(status=Item.Status.AVAILABLE).count(), 3)

    def test_active_reservation_is_left_alone(self):
        bundle = services.create_bundle(self.buyer, [self.items[0].id, self.items[1].id])
        services.reserve_bundle(bundle.id)
        self.assertEqual(services.release_expired_reservations(), 0)
        bundle.refresh_from_db()
        self.assertEqual(bundle.status, Bundle.Status.RESERVED)
