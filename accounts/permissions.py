from rest_framework.permissions import BasePermission


class IsAdminOrEmployee(BasePermission):
    """
    Allows access only to admin or employee users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            "admin",
            "employee",
        ]
