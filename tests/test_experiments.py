from django.test import SimpleTestCase

from bundles.experiments import assign_variant


class ExperimentTests(SimpleTestCase):
    def test_same_user_always_gets_same_variant(self):
        self.assertEqual({assign_variant(42) for _ in range(20)}, {assign_variant(42)})

    def test_both_variants_are_used_and_split_is_roughly_even(self):
        variants = [assign_variant(user_id) for user_id in range(1, 2001)]
        share_a = variants.count("A") / len(variants)
        self.assertTrue(0.45 < share_a < 0.55, share_a)

    def test_different_experiment_names_split_differently(self):
        a = [assign_variant(i, "exp_one") for i in range(200)]
        b = [assign_variant(i, "exp_two") for i in range(200)]
        self.assertNotEqual(a, b)
