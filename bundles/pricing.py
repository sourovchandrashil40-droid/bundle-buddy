"""Bundle pricing.

Kept free of Django imports on purpose: it is a pure function over integers, so it
can be tested in isolation and extracted into its own service later.
All money is integer cents; discounts are integer basis points (100 bps = 1%).
"""

from dataclasses import dataclass

# (minimum items, discount in basis points) - checked from the highest tier down.
DISCOUNT_TIERS = {
    "A": [(3, 1000), (2, 500)],
    "B": [(4, 1200), (3, 800), (2, 300)],
}


@dataclass(frozen=True)
class BundlePrice:
    subtotal_cents: int
    discount_bps: int
    discount_cents: int
    total_cents: int


def calculate(prices_cents, variant):
    if variant not in DISCOUNT_TIERS:
        raise ValueError(f"Unknown variant: {variant!r}")
    if not prices_cents:
        raise ValueError("At least one price is required")
    if any((not isinstance(p, int)) or p < 0 for p in prices_cents):
        raise ValueError("Prices must be non-negative integers (cents)")

    subtotal = sum(prices_cents)
    count = len(prices_cents)
    bps = next((rate for minimum, rate in DISCOUNT_TIERS[variant] if count >= minimum), 0)
    discount = subtotal * bps // 10_000  # floor: never discount more than promised
    return BundlePrice(subtotal, bps, discount, subtotal - discount)
