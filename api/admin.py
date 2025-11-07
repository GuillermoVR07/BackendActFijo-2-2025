# api/admin.py

from django.contrib import admin
from .models import *

# --- Admin Personalizado para Modelos Clave ---

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nit', 'fecha_creacion')
    search_fields = ('nombre', 'nit')
    readonly_fields = ('id', 'fecha_creacion')

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('get_nombre_completo', 'empresa', 'cargo', 'departamento')
    search_fields = ('usuario__first_name', 'apellido_p', 'ci', 'empresa__nombre')
    list_filter = ('empresa', 'cargo', 'departamento')
    readonly_fields = ('id',)

    @admin.display(description='Nombre Completo', ordering='usuario__first_name')
    def get_nombre_completo(self, obj):
        return f"{obj.usuario.first_name} {obj.apellido_p}"

@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'usuario', 'accion', 'ip_address', 'tenant_id')
    list_filter = ('usuario', 'accion')
    search_fields = ('detalle', 'ip_address')
    readonly_fields = [f.name for f in Log._meta.fields] # Hace todos los campos de solo lectura

    def has_add_permission(self, request):
        return False # No se pueden añadir logs manualmente

    def has_change_permission(self, request, obj=None):
        return False # No se pueden modificar logs

    def has_delete_permission(self, request, obj=None):
        return False # No se pueden borrar logs

# --- Admin para Modelos Dependientes de Empresa ---
# Este formato nos permite ver a qué empresa pertenece cada registro en la lista

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa')
    list_filter = ('empresa',)

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa')
    list_filter = ('empresa',)

@admin.register(Roles)
class RolesAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa')
    list_filter = ('empresa',)
    filter_horizontal = ('permisos',) # Facilita la asignación de permisos

@admin.register(ActivoFijo)
class ActivoFijoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_interno', 'empresa', 'estado')
    list_filter = ('empresa', 'estado')

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nit', 'pais', 'empresa', 'estado')
    list_filter = ('empresa', 'estado', 'pais')

@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'departamento', 'monto', 'fecha')
    list_filter = ('departamento',)

# --- Registro de Modelos Simples ---
# Estos modelos no necesitan tanta personalización en el admin

admin.site.register(Permisos)
admin.site.register(Estado)
admin.site.register(Ubicacion)
# ... y así registrarías el resto de tus modelos si los tuvieras