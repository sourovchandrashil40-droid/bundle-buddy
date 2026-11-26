"""Tiny counters stored in the cache (Redis in production)."""

from django.core.cache import cache

COUNTERS = [
    "bundles_created",
    "reservations_succeeded",
    "reservations_conflicted",
    "reservations_released",
    "catalogue_cache_hit",
    "catalogue_cache_miss",
]


def incr(name, amount=1):
    key = f"metrics:{name}"
    cache.add(key, 0, timeout=None)  # no-op if it already exists
    cache.incr(key, amount)


def snapshot():
    data = {name: cache.get(f"metrics:{name}", 0) for name in COUNTERS}
    lookups = data["catalogue_cache_hit"] + data["catalogue_cache_miss"]
    data["catalogue_cache_hit_rate"] = round(data["catalogue_cache_hit"] / lookups, 3) if lookups else None
    return data
