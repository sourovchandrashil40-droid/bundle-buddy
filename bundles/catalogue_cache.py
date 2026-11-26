"""Seller catalogue cache keys.

Each seller has a version number baked into the cache key. When an item changes
status we bump the version, which invalidates every cached page for that seller
at once without having to know how many pages exist.
"""

from django.core.cache import cache


def _version_key(seller_id):
    return f"catalogue:{seller_id}:version"


def page_key(seller_id, page):
    version = cache.get(_version_key(seller_id), 1)
    return f"catalogue:{seller_id}:v{version}:page:{page}"


def invalidate(seller_id):
    key = _version_key(seller_id)
    cache.add(key, 1, timeout=None)
    cache.incr(key)
