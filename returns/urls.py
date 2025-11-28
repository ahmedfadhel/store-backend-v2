from django.urls import path
from .views import ReturnRequestListCreateView, ReturnRequestDetailView

urlpatterns = [
    path("", ReturnRequestListCreateView.as_view(), name="returnrequest-list-create"),
    path("<int:pk>/", ReturnRequestDetailView.as_view(), name="returnrequest-detail"),
]
