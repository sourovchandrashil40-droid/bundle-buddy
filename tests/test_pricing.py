from django.test import SimpleTestCase

from bundles import pricing


class PricingTests(SimpleTestCase):
    def test_single_item_has_no_discount(self):
        result = pricing.calculate([1000], "A")
        self.assertEqual((result.discount_cents, result.total_cents), (0, 1000))

    def test_variant_a_tiers(self):
        self.assertEqual(pricing.calculate([1000, 1000], "A").discount_cents, 100)  # 5%
        self.assertEqual(pricing.calculate([1000] * 3, "A").discount_cents, 300)  # 10%
        self.assertEqual(pricing.calculate([1000] * 10, "A").discount_bps, 1000)  # capped at 10%

    def test_variant_b_tiers(self):
        self.assertEqual(pricing.calculate([1000, 1000], "B").discount_bps, 300)
        self.assertEqual(pricing.calculate([1000] * 3, "B").discount_bps, 800)
        self.assertEqual(pricing.calculate([1000] * 4, "B").discount_bps, 1200)
        self.assertEqual(pricing.calculate([1000] * 9, "B").discount_bps, 1200)

    def test_discount_is_floored_to_whole_cents(self):
        result = pricing.calculate([333, 334], "A")  # 667 * 5% = 33.35 cents
        self.assertEqual(result.discount_cents, 33)
        self.assertEqual(result.total_cents, 634)

    def test_total_plus_discount_equals_subtotal(self):
        result = pricing.calculate([199, 249, 1001], "B")
        self.assertEqual(result.total_cents + result.discount_cents, result.subtotal_cents)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            pricing.calculate([], "A")
        with self.assertRaises(ValueError):
            pricing.calculate([1000, 1000], "C")
        with self.assertRaises(ValueError):
            pricing.calculate([10.5, 1000], "A")  # floats are not allowed
        with self.assertRaises(ValueError):
            pricing.calculate([-5, 1000], "A")
