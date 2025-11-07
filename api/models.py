# api/models.py
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

def upload_path_perfil(instance, filename):
    """
    Guarda la foto de perfil en una carpeta específica del tenant.
    Ruta: /media/tenant_<empresa_id>/fotos_perfil/<filename>
    """
    return f'tenant_{instance.empresa.id}/fotos_perfil/{filename}'

def upload_path_activo(instance, filename):
    """
    Guarda la foto del activo en una carpeta específica del tenant.
    Ruta: /media/tenant_<empresa_id>/fotos_activos/<filename>
    """
    return f'tenant_{instance.empresa.id}/fotos_activos/{filename}'

class Empresa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=100, unique=True)
    nit = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=100, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    divisa_base = models.ForeignKey('Divisa', on_delete=models.SET_NULL, null=True, blank=True, related_name='empresas_base')
    def __str__(self): return self.nombre

class Divisa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=50, unique=True)
    codigo = models.CharField(max_length=3, unique=True)  # Ej: USD, EUR, BOB
    simbolo = models.CharField(max_length=5)
    tasa_cambio = models.DecimalField(max_digits=14, decimal_places=6) # Tasa respecto a una divisa de referencia global (ej. USD)

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

class Departamento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='departamentos')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    class Meta: unique_together = ('empresa', 'nombre')
    def __str__(self): return f"{self.nombre} ({self.empresa.nombre})"

class Permisos(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField()
    def __str__(self): return self.nombre

class Roles(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='roles')
    nombre = models.CharField(max_length=100)
    permisos = models.ManyToManyField(Permisos, blank=True)
    class Meta: unique_together = ('empresa', 'nombre')
    def __str__(self): return f"{self.nombre} ({self.empresa.nombre})"

class Cargo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='cargos')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    class Meta: unique_together = ('empresa', 'nombre')
    def __str__(self): return f"{self.nombre} ({self.empresa.nombre})"

class Empleado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='empleados')
    ci = models.CharField(max_length=20)
    apellido_p = models.CharField(max_length=100)
    apellido_m = models.CharField(max_length=100)
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    sueldo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cargo = models.ForeignKey(Cargo, on_delete=models.SET_NULL, null=True, blank=True)
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True, blank=True)
    roles = models.ManyToManyField(Roles, blank=True)
    
    foto_perfil = models.ImageField(upload_to=upload_path_perfil, null=True, blank=True)

    theme_preference = models.CharField(
        max_length=10,
        blank=True,         # Puede estar vacío
        null=True,          # Puede ser nulo en la BD
        default='dark'      # Valor por defecto si no se especifica
    )
    # Guardamos el color hexadecimal si el tema es 'custom'
    theme_custom_color = models.CharField(
        max_length=7,       # Formato '#RRGGBB'
        blank=True,
        null=True,
        default='#6366F1'   # Color índigo por defecto
    )
    # Guardamos si el efecto glow está activado
    theme_glow_enabled = models.BooleanField(default=False)
    # --- [FIN DE NUEVOS CAMPOS] ---

    def __str__(self):
        return f"{self.usuario.first_name} {self.apellido_p}"

class ActivoFijo(models.Model): 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='activos_fijos')
    nombre = models.CharField(max_length=100)
    codigo_interno = models.CharField(max_length=50)
    serial = models.CharField(max_length=255, blank=True, null=True, unique=True)
    fecha_adquisicion = models.DateField()
    valor_actual = models.DecimalField(max_digits=12, decimal_places=2)
    vida_util = models.IntegerField() # En años
    item_catalogo = models.ForeignKey('ItemCatalogo', on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.SET_NULL, # Si se borra el depto, el campo queda nulo
        null=True,    # Permite valores nulos en la BD
        blank=True,   # Permite que esté vacío en formularios
        related_name='activos' # Permite buscar activos desde un depto
    )
    estado = models.ForeignKey('Estado', on_delete=models.PROTECT) # Ej: "En Uso", "En Mantenimiento", "De Baja"
    proveedor = models.ForeignKey('Proveedor', on_delete=models.SET_NULL, null=True, blank=True)
    
    # --- [NUEVO] Campo de foto de activo opcional ---
    foto_activo = models.ImageField(upload_to=upload_path_activo, null=True, blank=True)
    
    class Meta: unique_together = ('empresa', 'codigo_interno')
    def __str__(self): return self.nombre

class PartidasPresupuestarias(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='partidas_presupuestarias')
    presupuesto = models.ForeignKey('Presupuesto', on_delete=models.CASCADE, related_name='partidas')
    nombre = models.CharField(max_length=20)
    fecha = models.DateField()

    def __str__(self):
        return self.nombre

class DetalleCompra(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='detalles_compra')
    orden_compra = models.ForeignKey('OrdenesCompra', on_delete=models.CASCADE, related_name='detalles')
    partida = models.ForeignKey('PartidasPresupuestarias', on_delete=models.CASCADE, related_name='detalles_compra')
    item = models.ForeignKey('ItemCatalogo', on_delete=models.PROTECT, related_name='en_compras')
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Compra de {self.cantidad} a {self.precio_unitario}"

class ItemCatalogo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='items_catalogo')
    nombre = models.CharField(max_length=200)
    tipo_item = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre

class Estado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='estados_activos')
    nombre = models.CharField(max_length=50) # Ej: "En Uso", "En Reparación", "Obsoleto"
    detalle = models.TextField(blank=True, null=True)
    def __str__(self): return self.nombre

class Ubicacion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='ubicaciones')
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    detalle = models.TextField(blank=True, null=True)
    def __str__(self): return self.nombre

class Inventario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='inventarios')
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='inventarios')
    item_catalogo = models.ForeignKey('ItemCatalogo', on_delete=models.CASCADE, related_name='inventarios')
    detalle_compra = models.ForeignKey('DetalleCompra', on_delete=models.CASCADE, related_name='inventarios')
    responsable = models.ForeignKey('Empleado', on_delete=models.SET_NULL, null=True, blank=True, related_name='inventarios_asignados')
    cantidad = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Inventario en {self.ubicacion.nombre}: {self.cantidad}"

class MovimientoInventario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE, related_name='movimientos')
    
    TIPO_MOVIMIENTO_CHOICES = [('ENTRADA', 'Entrada'), ('SALIDA', 'Salida'), ('AJUSTE', 'Ajuste')]
    
    tipo_movimiento = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES)
    fecha = models.DateField(auto_now_add=True)
    descripcion = models.CharField(max_length=50, blank=True)
    cantidad = models.IntegerField()

    def __str__(self):
        return f"{self.get_tipo_movimiento_display()} de {self.cantidad} en {self.inventario.item_catalogo.nombre}"

class Proveedor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='proveedores')
    nombre = models.CharField(max_length=100)
    nit = models.CharField(max_length=20)
    email = models.EmailField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    pais = models.CharField(max_length=50, blank=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=20, default='activo')
    def __str__(self): return self.nombre

class OrdenesCompra(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='ordenes_compra')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_compra')
    solicitante = models.ForeignKey('Empleado', on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_solicitadas')
    
    ESTADO_CHOICES = [('PENDIENTE', 'Pendiente'), ('APROBADA', 'Aprobada'), ('COMPLETADA', 'Completada'), ('CANCELADA', 'Cancelada')]
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    condiciones = models.TextField(blank=True)
    monto_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    def __str__(self):
        return f"Orden de Compra {self.id} para {self.empresa.nombre}"

class Impuestos(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=30, unique=True)
    cantidad = models.DecimalField(max_digits=5, decimal_places=2) # Ej. 13.00 para 13%

    def __str__(self):
        return f"{self.nombre} ({self.cantidad}%)"

class DisposicionActivos(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activo = models.ForeignKey(ActivoFijo, on_delete=models.CASCADE, related_name='disposiciones')
    impuesto = models.ForeignKey(Impuestos, on_delete=models.SET_NULL, null=True, blank=True, related_name='disposiciones')
    motivo = models.CharField(max_length=50)
    fecha = models.DateField()
    valor_disposicion = models.DecimalField(max_digits=12, decimal_places=2)
    detalle = models.TextField(blank=True)

    def __str__(self):
        return f"Disposición de {self.activo.nombre} por {self.motivo}"

class Presupuesto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE, related_name='presupuestos')
    monto = models.DecimalField(max_digits=15, decimal_places=2)
    fecha = models.DateField()
    descripcion = models.TextField(blank=True, null=True)
    def __str__(self): return f"Presupuesto {self.departamento.nombre} - {self.fecha}"

class Mantenimiento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='mantenimientos')
    activo = models.ForeignKey(ActivoFijo, on_delete=models.CASCADE, related_name='mantenimientos')
    empleado_asignado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True, related_name='mantenimientos_asignados')
    
    TIPO_CHOICES = [('PREVENTIVO', 'Preventivo'), ('CORRECTIVO', 'Correctivo')]
    ESTADO_CHOICES = [('PENDIENTE', 'Pendiente'), ('EN_PROGRESO', 'En Progreso'), ('COMPLETADO', 'Completado')]
    
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='CORRECTIVO')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    descripcion_problema = models.TextField()
    notas_solucion = models.TextField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.activo.nombre} ({self.get_estado_display()})"

class Suscripcion(models.Model):
    PLAN_CHOICES = [
        ('basico', 'Básico'),
        ('profesional', 'Profesional'),
        ('empresarial', 'Empresarial'),
    ]
    ESTADO_CHOICES = [
        ('activa', 'Activa'),
        ('vencida', 'Vencida'),
        ('cancelada', 'Cancelada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='suscripcion')
    
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='basico')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activa')
    
    fecha_inicio = models.DateField(default=timezone.now)
    fecha_fin = models.DateField() # Se calculará al crear
    
    # Límites del plan
    max_usuarios = models.PositiveIntegerField(default=5)
    max_activos = models.PositiveIntegerField(default=50)

    def __str__(self):
        return f"Suscripción {self.get_plan_display()} de {self.empresa.nombre} ({self.get_estado_display()})"

class RevalorizacionActivo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='revalorizaciones')
    activo = models.ForeignKey(ActivoFijo, on_delete=models.CASCADE, related_name='revalorizaciones')
    
    fecha = models.DateTimeField(auto_now_add=True)
    valor_anterior = models.DecimalField(max_digits=12, decimal_places=2)
    valor_nuevo = models.DecimalField(max_digits=12, decimal_places=2)
    factor_aplicado = models.DecimalField(max_digits=10, decimal_places=6)
    notas = models.TextField(blank=True, null=True)
    
    realizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"Revalorización de {self.activo.nombre} en {self.fecha.strftime('%Y-%m-%d')}"

class TipoDepreciacion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='tipos_depreciacion')
    nombre = models.CharField(max_length=20, unique=True)
    detalle = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.nombre

class DepreciacionActivos(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activo = models.ForeignKey(ActivoFijo, on_delete=models.CASCADE, related_name='depreciaciones')
    tipo_depreciacion = models.ForeignKey(TipoDepreciacion, on_delete=models.PROTECT, related_name='depreciaciones')
    fecha = models.DateField()
    monto = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Depreciación de {self.activo.nombre} - {self.monto}"

class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('ADVERTENCIA', 'Advertencia'),
        ('INFO', 'Info'),
        ('ERROR', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinatario = models.ForeignKey(
        User,
        on_delete=models.CASCADE, # Si se borra el usuario, se borran sus notificaciones
        related_name='notificaciones'
    )
    #empresa = model.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='notificaciones')
    
    timestamp = models.DateTimeField(auto_now_add=True)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='INFO')
    leido = models.BooleanField(default=False)
    url_destino = models.CharField(max_length=255, blank=True, null=True) # Ej: '/app/suscripcion'

    class Meta:
        ordering = ['leido', '-timestamp']

    def __str__(self):
        return f"[{self.get_tipo_display()}] para {self.destinatario.username} (Leído: {self.leido})"

class Log(models.Model):
    """
    Representa una entrada en la bitácora del sistema. Cada instancia es un registro
    de una acción importante realizada por un usuario.
    """
    # Clave primaria única para cada registro de log.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Registra automáticamente la fecha y hora exactas en que se creó el log.
    timestamp = models.DateTimeField(auto_now_add=True)

    # Guarda qué usuario realizó la acción.
    # Si se borra el usuario, el log no se borra, solo se quita la asociación (SET_NULL).
    # db_constraint=False es importante porque este modelo está pensado para vivir
    # en una base de datos separada ('log_saas') y no se puede crear una restricción
    # de clave foránea a nivel de base de datos entre distintas bases de datos.
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_constraint=False
    )

    # Guarda la dirección IP desde donde el usuario realizó la acción (útil para auditoría).
    ip_address = models.GenericIPAddressField()

    # Un texto que describe la acción, por ejemplo: "CREAR: ActivoFijo, ID: xxx"
    accion = models.CharField(max_length=255)

    # En un sistema multi-empresa (SaaS), esto guarda el ID de la empresa (tenant)
    # a la que pertenecen los datos que se modificaron.
    tenant_id = models.UUIDField(null=True, blank=True, db_index=True)

    # Un campo JSON muy potente para guardar datos adicionales. Por ejemplo,
    # al crear un activo, aquí se podría guardar una copia de los datos creados.
    payload = models.JSONField(null=True, blank=True)
    
    class Meta:
        # Le da un nombre explícito a la tabla en la base de datos 'log_saas'.
        db_table = 'log_bitacora'

class PrediccionMantenimiento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    tenant_id = models.UUIDField(db_index=True) # ID de la Empresa
    activo_id = models.UUIDField(db_index=True) # ID del ActivoFijo
    
    probabilidad_fallo = models.FloatField() # Probabilidad de fallo (0.0 a 1.0)
    dias_restantes_sugeridos = models.IntegerField(null=True, blank=True)
    razon = models.TextField(blank=True) # Explicación de la IA
    
    class Meta:
        ordering = ['-timestamp']
        db_table = 'prediccion_mantenimiento' # Nombre para la BD 'analytics_saas'

class PrediccionPresupuesto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    tenant_id = models.UUIDField(db_index=True) # ID de la Empresa
    departamento_id = models.UUIDField(db_index=True) # ID del Departamento
    
    monto_sugerido = models.DecimalField(max_digits=15, decimal_places=2)
    monto_anterior = models.DecimalField(max_digits=15, decimal_places=2)
    porcentaje_cambio = models.FloatField()
    razon = models.TextField(blank=True) # Explicación de la IA
    
    class Meta:
        ordering = ['-timestamp']
        db_table = 'prediccion_presupuesto' # Nombre para la BD 'analytics_saas'