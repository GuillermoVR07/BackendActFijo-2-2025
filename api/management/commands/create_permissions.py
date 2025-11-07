# management/commands/create_permissions.py
from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import Permisos

# --- [EDITADO] LISTA DE PERMISOS A CREAR ---
PERMISSIONS_LIST = [
    # General
    ('view_dashboard', 'Ver el Dashboard principal'),
    
    # Activos Fijos y su ciclo de vida
    ('view_activofijo', 'Ver la lista de activos fijos'),
    ('manage_activofijo', 'Crear, editar y eliminar activos fijos'),
    ('view_revalorizacion', 'Ver el historial de revalorizaciones de activos'),
    ('manage_revalorizacion', 'Ejecutar el proceso de revalorización de activos'),
    ('view_depreciacion', 'Ver el historial de depreciaciones de activos'),
    ('manage_depreciacion', 'Ejecutar el proceso de depreciación de activos'),
    ('view_disposicion', 'Ver las disposiciones (bajas) de activos'),
    ('manage_disposicion', 'Ejecutar la baja de un activo'),

    # Compras y Presupuestos
    ('view_presupuesto', 'Ver los presupuestos asignados'),
    ('manage_presupuesto', 'Crear, editar y eliminar presupuestos'),
    ('view_ordencompra', 'Ver la lista de órdenes de compra'),
    ('manage_ordencompra', 'Crear, editar y aprobar órdenes de compra'),

    # Inventario y Catálogo
    ('view_inventario', 'Ver el estado del inventario'),
    ('manage_inventario', 'Crear items de inventario y registrar movimientos'),
    ('view_itemcatalogo', 'Ver el catálogo de items'),
    ('manage_itemcatalogo', 'Crear y editar items en el catálogo'),

    # Mantenimiento
    ('view_mantenimiento', 'Ver la lista de mantenimientos'),
    ('manage_mantenimiento', 'Crear, editar y gestionar mantenimientos'),
    ('update_assigned_mantenimiento', 'Actualizar estado/notas de mantenimientos asignados'),

    # Organización y Empleados
    ('view_departamento', 'Ver la lista de departamentos'),
    ('manage_departamento', 'Crear, editar y eliminar departamentos'),
    ('view_cargo', 'Ver la lista de cargos'),
    ('manage_cargo', 'Crear, editar y eliminar cargos'),
    ('view_empleado', 'Ver la lista de empleados'),
    ('manage_empleado', 'Crear, editar y eliminar empleados'),
    
    # Roles y Permisos
    ('view_rol', 'Ver la lista de roles de la empresa'),
    ('manage_rol', 'Crear, editar y eliminar roles (y asignar permisos)'),
    ('view_permiso', 'Ver la lista de permisos globales (para asignar a roles)'),

    # Configuración General
    ('view_ubicacion', 'Ver la lista de ubicaciones'),
    ('manage_ubicacion', 'Crear, editar y eliminar ubicaciones'),
    ('view_proveedor', 'Ver la lista de proveedores'),
    ('manage_proveedor', 'Crear, editar y eliminar proveedores'),
    ('view_estadoactivo', 'Ver los estados de activos'),
    ('manage_estadoactivo', 'Crear, editar y eliminar estados de activos'),
    ('view_divisa', 'Ver la lista de divisas globales'),
    ('manage_divisa', 'Crear y editar divisas globales'),
    ('view_impuestos', 'Ver la lista de impuestos globales'),
    ('manage_impuestos', 'Crear y editar impuestos globales'),
    ('view_tipodepreciacion', 'Ver los tipos de depreciación'),
    ('manage_tipodepreciacion', 'Crear y editar tipos de depreciación'),

    # Reportes y Sistema
    ('view_reporte', 'Acceder a la sección de reportes y generar vistas previas'),
    ('export_reporte', 'Exportar reportes a PDF/Excel'),
    ('view_suscripcion', 'Ver el plan de suscripción actual de la empresa'),
    ('manage_suscripcion', 'Cambiar o actualizar el plan de suscripción (Admin)'),
    ('view_log', 'Ver la bitácora de acciones del sistema'),
    ('manage_settings', 'Acceder a la configuración general del sistema'),
]

class Command(BaseCommand):
    help = 'Crea o actualiza los permisos globales definidos en PERMISSIONS_LIST.'

    @transaction.atomic(using='default') 
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE('Verificando y creando permisos globales...'))
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        perm_names_in_list = {p[0] for p in PERMISSIONS_LIST}

        # Borrar permisos obsoletos que ya no están en la lista
        obsolete_perms = Permisos.objects.exclude(nombre__in=perm_names_in_list)
        delete_count = obsolete_perms.count()
        if delete_count > 0:
            obsolete_perms.delete()
            self.stdout.write(self.style.WARNING(f'  Eliminados {delete_count} permisos obsoletos.'))

        # Crear o actualizar permisos de la lista
        for perm_name, perm_desc in PERMISSIONS_LIST:
            permission, created = Permisos.objects.get_or_create(
                nombre=perm_name,
                defaults={'descripcion': perm_desc}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Creado: {perm_name}'))
                created_count += 1
            elif permission.descripcion != perm_desc:
                permission.descripcion = perm_desc
                permission.save()
                self.stdout.write(self.style.WARNING(f'  Actualizado desc: {perm_name}'))
                updated_count += 1
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nProceso completado.'))
        self.stdout.write(f'  Creados: {created_count}')
        self.stdout.write(f'  Actualizados: {updated_count}')
        self.stdout.write(f'  Omitidos (sin cambios): {skipped_count}')