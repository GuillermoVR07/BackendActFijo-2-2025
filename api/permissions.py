# api/permissions.py
from rest_framework import permissions

class HasPermission(permissions.BasePermission):
    """
    Custom permission to check if the user has a specific named permission
    through any of their assigned roles.
    """
    def __init__(self, required_permission):
        self.required_permission = required_permission
        super().__init__()

    def has_permission(self, request, view):
        # --- [NUEVO] El SuperAdmin siempre tiene permiso ---
        if request.user and request.user.is_staff:
            return True

        # Siempre permite métodos seguros (GET, HEAD, OPTIONS) para usuarios autenticados
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        # For unsafe methods (POST, PUT, PATCH, DELETE), check for the required permission
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            empleado = request.user.empleado
            # Check if any role assigned to the employee has the required permission
            # Note: This requires optimizing permission lookup if performance becomes an issue
            # (e.g., caching permissions per user session)
            has_perm = empleado.roles.filter(permisos__nombre=self.required_permission).exists()
            # print(f"DEBUG: Checking {self.required_permission} for {request.user}: {has_perm}") # Optional debug
            return has_perm
        except AttributeError: # Handle cases where user might not have 'empleado' linked yet
             return False
        except Exception as e: # Catch other potential errors
             print(f"ERROR checking permission {self.required_permission}: {e}")
             return False

    # Optional: Implement has_object_permission if you need row-level checks
    # def has_object_permission(self, request, view, obj):
    #     # ... logic to check permission against a specific object ...
    #     return super().has_object_permission(request, view, obj)
def check_permission(request, view, permission_name):
    """ Instantiates and checks HasPermission """
    checker = HasPermission(permission_name)
    return checker.has_permission(request, view)