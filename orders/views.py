from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from orders.models import Order
from orders.serializers import OrderSerializer, CreateOrderFromCartSerializer
from accounts.permissions import IsAdminOrEmployee


# --------- Create order from cart (customer or admin) ---------


class CreateOrderFromCartView(generics.CreateAPIView):
    """
    POST: create order from cart.
    - Normal users: order_type is forced to 'normal'.
    - Admin/employee: can create wholesale / replacement / exchange / cancellation.
    """

    serializer_class = CreateOrderFromCartSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user

        # If non-admin → force order_type to 'normal'
        data = serializer.validated_data
        if not (user.is_admin or user.is_employee):
            data["order_type"] = "normal"
        serializer._validated_data = data  # small hack to override
        self.order = serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = OrderSerializer(self.order)
        headers = self.get_success_headers(read_serializer.data)
        return Response(
            read_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


# --------- List & detail endpoints ---------


class OrderListView(generics.ListAPIView):
    """
    List orders for the current user.
    Admin can see all orders; normal users only their own.
    """

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.select_related("customer", "created_by").prefetch_related(
            "lines__variant", "lines__bundle"
        )
        user = self.request.user
        if user.is_admin or user.is_employee:
            return qs
        return qs.filter(customer=user)


class OrderDetailView(generics.RetrieveAPIView):
    """
    Retrieve a single order (must be customer or admin).
    """

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.select_related("customer", "created_by").prefetch_related(
            "lines__variant", "lines__bundle"
        )
        user = self.request.user
        if user.is_admin or user.is_employee:
            return qs
        return qs.filter(customer=user)


# --------- Admin-only: process restocking on issue orders ---------


class ProcessRestockingView(generics.UpdateAPIView):
    """
    Admin endpoint to trigger restocking on issue orders
    (replacement, exchange, cancellation).
    """

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]
    queryset = Order.objects.all()

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        order.process_restocking()
        serializer = self.get_serializer(order)
        return Response(serializer.data)
