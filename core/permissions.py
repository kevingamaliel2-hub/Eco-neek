from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    """Permite solo a admin crear/editar, otros solo lectura."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_superuser

class IsCentroAndSelfOrAdmin(permissions.BasePermission):
    """Permite a centros editar solo su propio perfil, admin puede todo."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return request.user.is_authenticated and request.user.is_centro and obj == request.user
