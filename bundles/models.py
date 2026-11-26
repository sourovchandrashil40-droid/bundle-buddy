from django.db import models


class Member(models.Model):
    """A Vinted-style user. Can be a seller, a buyer, or both."""

    username = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username


class Item(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available"
        RESERVED = "reserved"
        SOLD = "sold"

    seller = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="items")
    title = models.CharField(max_length=120)
    price_cents = models.PositiveIntegerField()  # money is always integer cents
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)
    reserved_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["seller", "status"]),  # seller catalogue query
            models.Index(fields=["status", "reserved_until"]),  # expiry sweep
        ]

    def __str__(self):
        return f"{self.title} ({self.price_cents}c)"


class Bundle(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        RESERVED = "reserved"
        EXPIRED = "expired"

    buyer = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="bundles_bought")
    seller = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="bundles_sold")
    variant = models.CharField(max_length=1)  # A/B experiment arm used for this price
    discount_bps = models.PositiveIntegerField()  # basis points: 500 = 5%
    subtotal_cents = models.PositiveIntegerField()
    discount_cents = models.PositiveIntegerField()
    total_cents = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reserved_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "reserved_until"])]


class BundleItem(models.Model):
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name="bundle_items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="bundle_items")
    price_cents = models.PositiveIntegerField()  # price snapshot at bundle creation

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["bundle", "item"], name="unique_item_per_bundle")
        ]
