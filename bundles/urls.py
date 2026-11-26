from django.urls import path

from . import views

urlpatterns = [
    path("sellers/<int:seller_id>/items/", views.seller_items),
    path("bundles/", views.create_bundle),
    path("bundles/<int:bundle_id>/reserve/", views.reserve_bundle),
    path("metrics/", views.metrics_view),
]
