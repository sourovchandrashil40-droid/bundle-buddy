import hashlib

EXPERIMENT_NAME = "bundle_discount_v1"


def assign_variant(user_id, experiment=EXPERIMENT_NAME):
    """Deterministic 50/50 split: the same user always gets the same variant."""
    digest = hashlib.sha256(f"{experiment}:{user_id}".encode()).hexdigest()
    return "A" if int(digest, 16) % 2 == 0 else "B"
