from django.urls import path
from .views import (
    CreateOrderFromCartView,
    OrderListView,
    OrderDetailView,
    ProcessRestockingView,
)

urlpatterns = [
    path("from-cart/", CreateOrderFromCartView.as_view(), name="order-from-cart"),
    path("", OrderListView.as_view(), name="order-list"),
    path("<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path(
        "<int:pk>/process-restocking/",
        ProcessRestockingView.as_view(),
        name="order-process-restocking",
    ),
]
