from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    message = 'No tienes permiso para realizar esta acción.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.rol == 'ADMIN'))


class IsAdminOrCajero(BasePermission):
    message = 'No tienes permiso para realizar esta acción.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.rol in {'ADMIN', 'CAJERO'}))


class BusinessQuerysetMixin:
    """Scopes model querysets by the authenticated user's business."""

    def get_queryset(self):
        queryset = super().get_queryset()
        business_id = getattr(self.request.user, 'negocio_id', None)
        return queryset.filter(negocio_id=business_id)
