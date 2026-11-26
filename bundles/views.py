import json
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import catalogue_cache, metrics, services
from .models import Item, Member
from .services import BundleError


def handle_errors(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except BundleError as exc:
            body = {"error": {"code": exc.code, "message": exc.message}}
            return JsonResponse(body, status=exc.status)

    return wrapper


def _json_body(request):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise BundleError("invalid_json", "Request body must be valid JSON.") from None
    if not isinstance(data, dict):
        raise BundleError("invalid_json", "Request body must be a JSON object.")
    return data


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _bundle_json(bundle):
    return {
        "id": bundle.id,
        "buyer_id": bundle.buyer_id,
        "seller_id": bundle.seller_id,
        "variant": bundle.variant,
        "item_ids": sorted(bundle.bundle_items.values_list("item_id", flat=True)),
        "subtotal_cents": bundle.subtotal_cents,
        "discount_percent": bundle.discount_bps / 100,
        "discount_cents": bundle.discount_cents,
        "total_cents": bundle.total_cents,
        "status": bundle.status,
        "reserved_until": bundle.reserved_until.isoformat() if bundle.reserved_until else None,
    }


@require_GET
def seller_items(request, seller_id):
    get_object_or_404(Member, pk=seller_id)
    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        page = 1

    key = catalogue_cache.page_key(seller_id, page)
    payload = cache.get(key)
    if payload is not None:
        metrics.incr("catalogue_cache_hit")
        return JsonResponse(payload)

    metrics.incr("catalogue_cache_miss")
    queryset = Item.objects.filter(seller_id=seller_id, status=Item.Status.AVAILABLE).order_by("id")
    paginator = Paginator(queryset, settings.CATALOGUE_PAGE_SIZE)
    page_obj = paginator.get_page(page)
    payload = {
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "items": [
            {"id": i.id, "title": i.title, "price_cents": i.price_cents} for i in page_obj.object_list
        ],
    }
    cache.set(key, payload, settings.CATALOGUE_CACHE_SECONDS)
    return JsonResponse(payload)


@csrf_exempt  # JSON API without sessions/cookies, so CSRF does not apply
@require_POST
@handle_errors
def create_bundle(request):
    data = _json_body(request)
    buyer_id, item_ids = data.get("buyer_id"), data.get("item_ids")
    if not _is_int(buyer_id) or not isinstance(item_ids, list) or not all(_is_int(i) for i in item_ids):
        raise BundleError("invalid_input", "Expected integer 'buyer_id' and a list of integer 'item_ids'.")
    buyer = Member.objects.filter(pk=buyer_id).first()
    if buyer is None:
        raise BundleError("buyer_not_found", "Buyer not found.", 404)
    bundle = services.create_bundle(buyer, item_ids)
    return JsonResponse(_bundle_json(bundle), status=201)


@csrf_exempt
@require_POST
@handle_errors
def reserve_bundle(request, bundle_id):
    bundle = services.reserve_bundle(bundle_id)
    return JsonResponse(_bundle_json(bundle))


@require_GET
def metrics_view(request):
    return JsonResponse(metrics.snapshot())
