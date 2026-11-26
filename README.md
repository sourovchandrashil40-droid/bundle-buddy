# BundleBuddy

[![CI](https://github.com/YOUR_USERNAME/bundle_buddy/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/bundle_buddy/actions)

A small Django JSON API for marketplace **bundle discounts**: a buyer picks several items from
one seller, gets a discounted price, and can reserve the items for 15 minutes.

Built as a learning project to practise backend fundamentals: relational modelling,
caching, safe concurrent updates, testing and CI.

**Stack:** Python 3.12, Django 5, MySQL 8, Redis 7, Docker Compose, GitHub Actions.

## Features
- Bundle pricing with integer cents only (no floats). Two discount variants (A/B experiment).
- Deterministic experiment assignment per user (hash of user id).
- All-or-nothing reservation that cannot be double-booked (atomic guarded `UPDATE`).
- Seller catalogue endpoint, paginated and cached in Redis for 60s, invalidated on change.
- Background command that releases expired reservations.
- JSON structured logs and a `/metrics` endpoint (reservations, cache hit rate).

## Business rules
| Variant | 2 items | 3 items | 4+ items |
|---|---|---|---|
| A | 5% | 10% | 10% |
| B | 3% | 8% | 12% |

All items must belong to the same seller, be `available`, and a bundle needs at least 2 different items.

## Run it
```bash
docker compose up --build
```
The API is then on http://localhost:8000 with demo data (seller id=1, buyer id=2, items 1-5).

Without Docker (SQLite + in-memory cache):
```bash
python -m venv .venv && source .venv/bin/activate
pip install Django django-redis          # mysqlclient is only needed for MySQL
python manage.py migrate && python manage.py seed_demo
python manage.py runserver
```

## Try it
```bash
# Seller catalogue (cached 60s)
curl localhost:8000/sellers/1/items/

# Create a bundle
curl -X POST localhost:8000/bundles/ -H 'Content-Type: application/json' \
     -d '{"buyer_id": 2, "item_ids": [1, 2, 3]}'

# Reserve it for 15 minutes
curl -X POST localhost:8000/bundles/1/reserve/

# Counters
curl localhost:8000/metrics/

# Release expired reservations manually (the worker container does this every minute)
docker compose exec web python manage.py release_expired_reservations
```

Example response from `POST /bundles/`:
```json
{"id": 1, "buyer_id": 2, "seller_id": 1, "variant": "A", "item_ids": [1, 2, 3],
 "subtotal_cents": 6200, "discount_percent": 10.0, "discount_cents": 620,
 "total_cents": 5580, "status": "pending", "reserved_until": null}
```

## Tests
```bash
python manage.py test      # 30+ tests: pricing, experiment, services, API
ruff check .
```

## Project layout
```
bundles/pricing.py          pure pricing logic (no Django imports)
bundles/experiments.py      A/B assignment
bundles/services.py         create / reserve / release use cases
bundles/catalogue_cache.py  versioned cache keys
bundles/views.py            thin HTTP layer
docs/decisions.md           why things are built this way
```

## What I would improve next
- Authentication instead of passing `buyer_id`.
- Celery beat instead of a shell loop for expiring reservations.
- A real concurrency test against MySQL with parallel threads.
- Prometheus/Datadog metrics export and request-id logging.
- Rate limiting on the write endpoints.
