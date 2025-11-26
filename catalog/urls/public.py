from django.urls import path, register_converter
from ..converters import ArabicSlugConverter

from ..views import (
    ProductListView,
    ProductDetailView,
    VariantListView,
    BundleListView,
    BundleDetailView,
)


# Register new convertor for the slug so it can handle arabic slug characters
register_converter(ArabicSlugConverter, "aslug")

urlpatterns = [
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<aslug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    path("variants/", VariantListView.as_view(), name="variant-list"),
    path("bundles/", BundleListView.as_view(), name="bundle-list"),
    path("bundles/<slug:slug>/", BundleDetailView.as_view(), name="bundle-detail"),
]
