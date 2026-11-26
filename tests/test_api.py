import json

from django.test import TestCase

from .helpers import make_buyer, make_seller_with_items, reset_cache


class ApiTests(TestCase):
    def setUp(self):
        reset_cache()
        self.seller, self.items = make_seller_with_items()
        self.buyer = make_buyer()

    def post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def test_create_bundle_returns_201_and_totals(self):
        response = self.post("/bundles/", {"buyer_id": self.buyer.id, "item_ids": [i.id for i in self.items]})
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["subtotal_cents"], 6000)
        self.assertEqual(body["total_cents"] + body["discount_cents"], 6000)
        self.assertEqual(body["status"], "pending")

    def test_create_bundle_validation_errors(self):
        self.assertEqual(self.post("/bundles/", {"buyer_id": "x", "item_ids": []}).status_code, 400)
        self.assertEqual(self.post("/bundles/", {"buyer_id": 9999, "item_ids": [1, 2]}).status_code, 404)
        response = self.client.post("/bundles/", data="not json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_json")

    def test_get_not_allowed_on_create(self):
        self.assertEqual(self.client.get("/bundles/").status_code, 405)

    def test_reserve_flow_and_conflict(self):
        ids = [self.items[0].id, self.items[1].id]
        first = self.post("/bundles/", {"buyer_id": self.buyer.id, "item_ids": ids}).json()
        other = make_buyer("other")
        second = self.post("/bundles/", {"buyer_id": other.id, "item_ids": ids}).json()

        ok = self.client.post(f"/bundles/{first['id']}/reserve/")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["status"], "reserved")

        conflict = self.client.post(f"/bundles/{second['id']}/reserve/")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["error"]["code"], "items_unavailable")

    def test_catalogue_lists_only_available_items_and_is_cached(self):
        url = f"/sellers/{self.seller.id}/items/"
        first = self.client.get(url).json()
        self.assertEqual(first["total_items"], 3)
        self.client.get(url)

        metrics = self.client.get("/metrics/").json()
        self.assertEqual(metrics["catalogue_cache_miss"], 1)
        self.assertEqual(metrics["catalogue_cache_hit"], 1)
        self.assertEqual(metrics["catalogue_cache_hit_rate"], 0.5)

    def test_reservation_invalidates_catalogue_cache(self):
        url = f"/sellers/{self.seller.id}/items/"
        self.assertEqual(self.client.get(url).json()["total_items"], 3)  # warms the cache

        ids = [self.items[0].id, self.items[1].id]
        bundle = self.post("/bundles/", {"buyer_id": self.buyer.id, "item_ids": ids}).json()
        self.client.post(f"/bundles/{bundle['id']}/reserve/")

        self.assertEqual(self.client.get(url).json()["total_items"], 1)

    def test_catalogue_unknown_seller_is_404(self):
        self.assertEqual(self.client.get("/sellers/9999/items/").status_code, 404)

    def test_catalogue_pagination(self):
        big_seller, _ = make_seller_with_items("big", tuple(range(100, 2600, 100)))  # 25 items
        page2 = self.client.get(f"/sellers/{big_seller.id}/items/?page=2").json()
        self.assertEqual((page2["page"], page2["total_pages"], len(page2["items"])), (2, 2, 5))
