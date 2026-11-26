# Design decisions

Short notes on the choices that matter, and what I would do differently at larger scale.

## 1. Money is integer cents, discounts are integer basis points
Floats cannot represent most decimal amounts exactly (`0.1 + 0.2 != 0.3`), which leads to
off-by-one-cent bugs. Prices are stored as `price_cents`, and discount rates as basis points
(500 = 5%). The discount is `subtotal * bps // 10_000`, which floors, so the buyer is never
given more discount than the tier promises.

## 2. Pricing is a pure module (`bundles/pricing.py`)
It has no Django imports: integers in, a small dataclass out. This is the piece I would extract
first if the app grew into a monolith, because it already has a clear interface and its own tests.

## 3. Reservations cannot be double-booked
Two buyers can try to reserve the same item at the same moment. A check-then-update
("is it available? yes -> reserve") has a race between the check and the update.
Instead, `reserve_bundle` runs one guarded statement:

    UPDATE item SET status='reserved' WHERE id IN (...) AND status='available'

The database applies this atomically per row. If the number of updated rows is lower than the
number of items, someone else got there first, so I raise inside `transaction.atomic()` and the
whole reservation rolls back (all-or-nothing). The bundle row is also locked with
`select_for_update()` so the same bundle cannot be reserved twice in parallel.

## 4. Deterministic A/B assignment
`sha256("experiment:user_id") % 2` means the same user always sees the same discount tier,
with no assignment table needed. The variant used is stored on each bundle, so results can be
analysed later. Changing the experiment name reshuffles users.

## 5. Catalogue cache uses a version number in the key
Cached pages are keyed `catalogue:<seller>:v<version>:page:<n>`. When an item changes state,
the seller's version is bumped, so every cached page becomes unreachable at once and expires
on its own after 60 seconds. This avoids having to track or delete individual page keys.

## 6. Expiry is a management command, not a task queue
`release_expired_reservations` is idempotent and safe to run repeatedly, so a loop in
docker compose (or cron) is enough for this scope. With higher volume I would move it to
Celery beat so that it is monitored and retried.

## 7. Money-related indexes
`(seller, status)` serves the catalogue query; `(status, reserved_until)` serves the expiry sweep.

## Known limitations
- No authentication: `buyer_id` is passed in the body. Real auth was left out on purpose.
- Nothing turns a reservation into a sale (no payments).
- Metrics are simple Redis counters, not a Prometheus/Datadog exporter.
