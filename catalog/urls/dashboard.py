from django.urls import path
from catalog import dashboard_views as views

urlpatterns = [
    # PRODUCTS
    path(
        "products/",
        views.DashboardProductListCreateView.as_view(),
        name="dashboard-product-list",
    ),
    path(
        "products/<int:pk>/",
        views.DashboardProductDetailView.as_view(),
        name="dashboard-product-detail",
    ),
    # VARIANTS
    path(
        "variants/",
        views.DashboardVariantListCreateView.as_view(),
        name="dashboard-variant-list",
    ),
    path(
        "variants/<int:pk>/",
        views.DashboardVariantDetailView.as_view(),
        name="dashboard-variant-detail",
    ),
    # VARIANT OPTIONS
    path(
        "option-values/",
        views.DashboardOptionValueListCreateView.as_view(),
        name="dashboard-optionvalue-list",
    ),
    path(
        "option-values/<int:pk>/",
        views.DashboardOptionValueDetailView.as_view(),
        name="dashboard-optionvalue-detail",
    ),
    # PRODUCT IMAGES
    path(
        "images/",
        views.DashboardProductImageListCreateView.as_view(),
        name="dashboard-image-list",
    ),
    path(
        "images/<int:pk>/",
        views.DashboardProductImageDetailView.as_view(),
        name="dashboard-image-detail",
    ),
    # BUNDLES
    path(
        "bundles/",
        views.DashboardBundleListCreateView.as_view(),
        name="dashboard-bundle-list",
    ),
    path(
        "bundles/<int:pk>/",
        views.DashboardBundleDetailView.as_view(),
        name="dashboard-bundle-detail",
    ),
    # Bundle Items (variant-level)
    path(
        "bundle-items/",
        views.DashboardBundleItemListCreateView.as_view(),
        name="dashboard-bundleitem-list",
    ),
    path(
        "bundle-items/<int:pk>/",
        views.DashboardBundleItemDetailView.as_view(),
        name="dashboard-bundleitem-detail",
    ),
    path(
        "tiers/",
        views.DashboardTieredPriceListCreateView.as_view(),
        name="dashboard-tier-list",
    ),
    path(
        "tiers/<int:pk>/",
        views.DashboardTieredPriceDetailView.as_view(),
        name="dashboard-tier-detail",
    ),
]
