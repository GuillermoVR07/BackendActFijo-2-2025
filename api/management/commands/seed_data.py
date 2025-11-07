# -*- coding: utf-8 -*-
import uuid
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# Importar todos los modelos necesarios del nuevo esquema
from api.models import (
    Empresa, Empleado, Departamento, Cargo, Roles, Permisos,
    Divisa, Estado, Ubicacion, Proveedor, ActivoFijo, Presupuesto,
    Suscripcion, Mantenimiento, Notificacion, ItemCatalogo, OrdenesCompra,
    DetalleCompra, PartidasPresupuestarias, Inventario, MovimientoInventario,
    TipoDepreciacion, DepreciacionActivos, DisposicionActivos, Impuestos, Log
)

PASSWORD = "admin123"

class Command(BaseCommand):
    help = """Limpia y puebla la base de datos con datos de ejemplo coherentes con el nuevo esquema."""

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Limpiando TODAS las bases de datos (default, log_saas, analytics_saas)...'))

        # --- LIMPIEZA DE DATOS EN ORDEN INVERSO DE DEPENDENCIAS ---
        # Limpiar la base de datos de logs y analytics
        Log.objects.using('log_saas').all().delete()

        # Limpiar la base de datos principal (default)
        DisposicionActivos.objects.all().delete()
        DepreciacionActivos.objects.all().delete()
        TipoDepreciacion.objects.all().delete()
        Mantenimiento.objects.all().delete()
        MovimientoInventario.objects.all().delete()
        Inventario.objects.all().delete()
        ActivoFijo.objects.all().delete()
        DetalleCompra.objects.all().delete()
        OrdenesCompra.objects.all().delete()
        PartidasPresupuestarias.objects.all().delete()
        Presupuesto.objects.all().delete()
        ItemCatalogo.objects.all().delete()
        Notificacion.objects.all().delete()
        Suscripcion.objects.all().delete()
        Empleado.objects.all().delete()
        User.objects.all().exclude(is_superuser=True).delete()
        Roles.objects.all().delete()
        Proveedor.objects.all().delete()
        Ubicacion.objects.all().delete()
        Estado.objects.all().delete()
        Cargo.objects.all().delete()
        Departamento.objects.all().delete()
        Empresa.objects.all().delete()
        
        # Limpiar modelos globales que no dependen de Empresa
        Divisa.objects.all().delete()
        Impuestos.objects.all().delete()
        # Permisos no se borra, se gestiona con 'create_permissions'

        self.stdout.write(self.style.SUCCESS('Bases de datos limpias.'))
        self.stdout.write(self.style.WARNING('Creando nuevos datos de ejemplo...'))

        # --- 1. CREAR DATOS GLOBALES ---
        divisa_usd, _ = Divisa.objects.get_or_create(codigo='USD', defaults={'nombre': 'Dólar Americano', 'simbolo': '$', 'tasa_cambio': Decimal('1.0')})
        divisa_bob, _ = Divisa.objects.get_or_create(codigo='BOB', defaults={'nombre': 'Boliviano', 'simbolo': 'Bs.', 'tasa_cambio': Decimal('6.96')})

        impuesto_iva, _ = Impuestos.objects.get_or_create(nombre='IVA', defaults={'cantidad': Decimal('13.0')})

        # --- 2. OBTENER PERMISOS --- 
        # (Asegúrate de haber corrido 'create_permissions' primero)
        permisos = Permisos.objects.all()

        # --- 3. CREAR DATOS PARA CADA EMPRESA ---
        self.crear_datos_empresa(
            nombre_empresa='Innovatech Solutions',
            nit='123456001',
            admin_user='admin_innovatech',
            divisa_base=divisa_bob,
            permisos=permisos
        )
        
        self.stdout.write(self.style.SUCCESS('¡Datos de ejemplo creados con éxito!'))
        self.stdout.write(self.style.NOTICE(f'--- Usuarios Admin Creados (Pass: {PASSWORD}) ---'))
        self.stdout.write('admin_innovatech')

    def crear_usuario(self, username, first_name, last_name, email):
        return User.objects.create_user(
            username=username, password=PASSWORD, first_name=first_name,
            last_name=last_name, email=email, is_active=True
        )

    def crear_empleado(self, user, empresa, ci, ap_p, ap_m, sueldo, cargo, depto):
        return Empleado.objects.create(
            usuario=user, empresa=empresa, ci=ci, apellido_p=ap_p,
            apellido_m=ap_m, sueldo=sueldo, cargo=cargo, departamento=depto
        )

    def crear_datos_empresa(self, nombre_empresa, nit, admin_user, divisa_base, permisos):
        # Empresa y Suscripción
        empresa = Empresa.objects.create(nombre=nombre_empresa, nit=nit, divisa_base=divisa_base)
        Suscripcion.objects.create(
            empresa=empresa, plan='profesional', estado='activa',
            fecha_fin=timezone.now() + timedelta(days=365),
            max_usuarios=20, max_activos=200
        )
        self.stdout.write(f'Creada Empresa: {empresa.nombre}')

        # Ubicaciones, Estados, Departamentos, Cargos
        ubi_principal = Ubicacion.objects.create(empresa=empresa, nombre='Oficina Central')
        estado_nuevo = Estado.objects.create(empresa=empresa, nombre='Nuevo')
        estado_en_uso = Estado.objects.create(empresa=empresa, nombre='En Uso')
        depto_ti = Departamento.objects.create(empresa=empresa, nombre='TI')
        depto_finanzas = Departamento.objects.create(empresa=empresa, nombre='Finanzas')
        cargo_admin_ti = Cargo.objects.create(empresa=empresa, nombre='Admin de TI')

        # Admin de la empresa
        user_admin = self.crear_usuario(admin_user, 'Admin', nombre_empresa, f'{admin_user}@example.com')
        empleado_admin = self.crear_empleado(user_admin, empresa, '1234567', 'Gomez', 'Perez', 5000, cargo_admin_ti, depto_ti)
        rol_admin = Roles.objects.create(empresa=empresa, nombre='Administrador')
        rol_admin.permisos.set(permisos) # Asignar todos los permisos
        empleado_admin.roles.add(rol_admin)

        # Catálogo de Items
        item_laptop = ItemCatalogo.objects.create(empresa=empresa, nombre='Laptop Dell XPS 15', tipo_item='Equipo de Computación')
        item_silla = ItemCatalogo.objects.create(empresa=empresa, nombre='Silla Ergonómica Herman Miller', tipo_item='Mobiliario')

        # Proveedor
        proveedor_local = Proveedor.objects.create(empresa=empresa, nombre='TechPro S.R.L.', nit='102030405')

        # Ciclo de Compra
        presupuesto_ti = Presupuesto.objects.create(departamento=depto_ti, monto=Decimal('10000.00'), fecha=timezone.now().date())
        partida_laptops = PartidasPresupuestarias.objects.create(empresa=empresa, presupuesto=presupuesto_ti, nombre='Compra Laptops', fecha=timezone.now().date())
        
        orden_compra = OrdenesCompra.objects.create(
            empresa=empresa, proveedor=proveedor_local, solicitante=empleado_admin, 
            estado='APROBADA', fecha_inicio=timezone.now().date()
        )
        
        detalle_compra_laptops = DetalleCompra.objects.create(
            empresa=empresa, orden_compra=orden_compra, partida=partida_laptops, 
            item=item_laptop, cantidad=5, precio_unitario=Decimal('1500.00')
        )
        orden_compra.monto_total = detalle_compra_laptops.cantidad * detalle_compra_laptops.precio_unitario
        orden_compra.save()

        # Inventario y Activos Fijos
        inv_laptop = Inventario.objects.create(
            empresa=empresa, ubicacion=ubi_principal, item_catalogo=item_laptop, 
            detalle_compra=detalle_compra_laptops, responsable=empleado_admin, cantidad=5
        )
        MovimientoInventario.objects.create(inventario=inv_laptop, tipo_movimiento='ENTRADA', cantidad=5, descripcion='Compra inicial')

        # Crear un Activo Fijo a partir de un item del inventario
        activo_laptop = ActivoFijo.objects.create(
            empresa=empresa, nombre=item_laptop.nombre, codigo_interno=f'{empresa.nombre[:4].upper()}-LT-001',
            serial='ABC123XYZ', fecha_adquisicion=timezone.now().date(), valor_actual=detalle_compra_laptops.precio_unitario,
            vida_util=3, item_catalogo=item_laptop, departamento=depto_ti, estado=estado_en_uso, proveedor=proveedor_local
        )
        inv_laptop.cantidad -= 1
        inv_laptop.save()
        MovimientoInventario.objects.create(inventario=inv_laptop, tipo_movimiento='SALIDA', cantidad=-1, descripcion=f'Asignado a Activo Fijo {activo_laptop.codigo_interno}')