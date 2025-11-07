# api/serializers.py
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from .permissions import check_permission, HasPermission
from .models import *
from django.db import transaction
from datetime import timedelta

class CurrentUserEmpresaDefault:
    requires_context = True

    def __call__(self, serializer_field):
        request = serializer_field.context['request']
        user = request.user
        if user.is_staff:
            empresa = Empresa.objects.first()
            if not empresa:
                raise serializers.ValidationError("No hay empresas registradas. El superusuario no puede crear datos.")
            return empresa
        
        if hasattr(user, 'empleado'):
            return user.empleado.empresa
        
        raise serializers.ValidationError("El usuario no está asociado a una empresa.")

class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = ['id', 'nombre', 'nit']

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        try:
            empleado = user.empleado
            token['username'] = user.username
            token['email'] = user.email
            token['nombre_completo'] = f"{user.first_name} {empleado.apellido_p}"
            token['empresa_id'] = str(empleado.empresa.id)
            token['empresa_nombre'] = empleado.empresa.nombre
            token['roles'] = [rol.nombre for rol in empleado.roles.all()]             
            token['is_admin'] = user.is_staff 
            token['empleado_id'] = str(empleado.id) # <-- ID del Empleado
            token['theme_preference'] = empleado.theme_preference
            token['theme_custom_color'] = empleado.theme_custom_color
            token['theme_glow_enabled'] = empleado.theme_glow_enabled
        except Empleado.DoesNotExist:
            token['username'] = user.username
            token['email'] = user.email
            token['nombre_completo'] = user.username
            token['empresa_id'] = None
            token['empresa_nombre'] = None
            token['roles'] = []
            token['is_admin'] = user.is_staff
            token['empleado_id'] = None
            token['theme_preference'] = None
            token['theme_custom_color'] = None
            token['theme_glow_enabled'] = None
        return token

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class CargoSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    class Meta:
        model = Cargo
        fields = '__all__'

    def validate(self, data):
        empresa = data.get('empresa')
        nombre = data.get('nombre')
        query = Cargo.objects.filter(empresa=empresa, nombre__iexact=nombre)

        if self.instance:
            query = query.exclude(pk=self.instance.pk)

        if query.exists():
            raise serializers.ValidationError({
                "nombre": f"Ya existe un cargo con el nombre '{nombre}' en la empresa '{empresa.nombre}'."
            })
            
        return data

class DepartamentoSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    class Meta:
        model = Departamento
        fields = '__all__'

class RolesSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    class Meta:
        model = Roles
        fields = '__all__'
        
class EmpleadoSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'}, required=False) # No requerido al editar
    first_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    
    roles = serializers.PrimaryKeyRelatedField(
        queryset=Roles.objects.all(), 
        many=True, 
        #write_only=True, 
        required=False
    )
    
    # --- [NUEVO] Campo de foto ---
    # DRF maneja ImageField (y FileField) automáticamente
    # Aceptará un archivo subido (multipart/form-data)
    foto_perfil = serializers.ImageField(required=False, allow_null=True)
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())

    class Meta:
        model = Empleado
        fields = [
            'id', 'usuario', 'ci', 'apellido_p', 'apellido_m', 
            'direccion', 'telefono', 'sueldo', 'cargo', 
            'departamento', 'empresa', 'foto_perfil', # <-- Añadido
            # Campos write_only
            'theme_preference', 'theme_custom_color', 'theme_glow_enabled',
            'username', 'password', 'first_name', 'email', 'roles', 
            # Campos read_only
            'cargo_nombre', 'departamento_nombre', 'roles_asignados' 
        ]      
        read_only_fields = ('usuario', 'cargo_nombre', 'departamento_nombre', 'roles_asignados')
        extra_kwargs = {
            'cargo': {'required': False, 'allow_null': True}, # <-- 'write_only: True' ELIMINADO
            'departamento': {'required': False, 'allow_null': True}, # <-- 'write_only: True' ELIMINADO
        }

    cargo_nombre = serializers.CharField(source='cargo.nombre', read_only=True, allow_null=True)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True, allow_null=True)
    roles_asignados = RolesSerializer(source='roles', many=True, read_only=True)

    def create(self, validated_data):
        # ... (Tu método create está bien) ...
        # (Asegúrate de que 'foto_perfil' se pase en validated_data)
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name')
        email = validated_data.pop('email')
        roles_data = validated_data.pop('roles', [])
        
        user = User.objects.create_user(
            username=username, password=password, first_name=first_name,
            email=email, last_name=validated_data.get('apellido_p', ''),
            is_active=True
        )
        
        # 'foto_perfil' y el resto de campos están en validated_data
        empleado = Empleado.objects.create(usuario=user, **validated_data) 
        if roles_data:
            empleado.roles.set(roles_data)
        return empleado

    def update(self, instance, validated_data):
        # Manejar la actualización de campos de User si se proporcionan
        # (Tu EmpleadoForm.jsx los deshabilita, lo cual está bien,
        # pero esto es por si quieres añadir "editar perfil" luego)
        
        # No se puede cambiar el username, pero sí otros datos
        user = instance.usuario
        user.first_name = validated_data.get('first_name', user.first_name)
        user.email = validated_data.get('email', user.email)
        user.last_name = validated_data.get('apellido_p', user.last_name)
        
        # Cambiar contraseña solo si se proporciona una nueva
        password = validated_data.pop('password', None)
        if password:
            user.set_password(password)
        user.save()
        
        # Manejar roles
        if 'roles' in validated_data:
            roles_data = validated_data.pop('roles')
            instance.roles.set(roles_data)
            
        # Actualizar el resto de campos del empleado
        return super().update(instance, validated_data)

class ActivoFijoSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    # --- [NUEVO] Campo de foto ---
    foto_activo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = ActivoFijo
        fields = '__all__' # Incluye 'foto_activo'

class PresupuestoSerializer(serializers.ModelSerializer):
    # Le decimos que anide la información del departamento al leer
    departamento = DepartamentoSerializer(read_only=True)
    # Al escribir, esperamos solo el ID del departamento
    departamento_id = serializers.PrimaryKeyRelatedField(
        queryset=Departamento.objects.all(), source='departamento', write_only=True
    )

    class Meta:
        model = Presupuesto
        fields = ['id', 'descripcion', 'monto', 'fecha', 'departamento', 'departamento_id']
        
class EstadoSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    class Meta:
        model = Estado
        fields = '__all__'

class UbicacionSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    class Meta:
        model = Ubicacion
        fields = '__all__'

class ProveedorSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    class Meta:
        model = Proveedor
        fields = '__all__'

class PermisosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permisos
        fields = '__all__'

class RegisterEmpresaSerializer(serializers.Serializer):
    # (Campos existentes)
    empresa_nombre = serializers.CharField(max_length=100)
    empresa_nit = serializers.CharField(max_length=20)
    admin_username = serializers.CharField(max_length=100)
    admin_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    admin_first_name = serializers.CharField(max_length=100)
    admin_email = serializers.EmailField()
    admin_ci = serializers.CharField(max_length=20)
    admin_apellido_p = serializers.CharField(max_length=100)
    admin_apellido_m = serializers.CharField(max_length=100)
    card_number = serializers.CharField(write_only=True)
    card_expiry = serializers.CharField(write_only=True)
    card_cvc = serializers.CharField(write_only=True)
    plan = serializers.ChoiceField(choices=Suscripcion.PLAN_CHOICES, write_only=True)    

    # ... (Tus métodos validate_... están perfectos) ...
    def validate_empresa_nombre(self, value):
        if Empresa.objects.filter(nombre__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una empresa con este nombre.")
        return value
        
    def validate_empresa_nit(self, value):
        if Empresa.objects.filter(nit__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una empresa con este NIT.")
        return value
        
    def validate_admin_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Este nombre de usuario ya está en uso.")
        return value

    @transaction.atomic(using='default')
    def create(self, validated_data):
        try:
            # 1. Crear la Empresa
            empresa = Empresa.objects.create(
                nombre=validated_data['empresa_nombre'],
                nit=validated_data['empresa_nit']
            )

            # 2. Crear el User (Admin)
            user = User.objects.create_user(
                username=validated_data['admin_username'],
                password=validated_data['admin_password'],
                first_name=validated_data['admin_first_name'],
                email=validated_data['admin_email'],
                last_name=validated_data['admin_apellido_p'],
                is_active=True
            )

            # 3. Crear el Empleado (Admin)
            empleado = Empleado.objects.create(
                usuario=user,
                empresa=empresa,
                ci=validated_data['admin_ci'],
                apellido_p=validated_data['admin_apellido_p'],
                apellido_m=validated_data['admin_apellido_m'],
                # Puedes añadir valores por defecto si quieres
                # cargo=Cargo.objects.get_or_create(...)[0],
            )

            # 4. Crear la Suscripción (Asegurando usar el plan validado)
            # validated_data['plan'] ya contiene el valor correcto ('basico', 'profesional', etc.)
            plan_seleccionado = validated_data['plan']
            limits = {
                'basico': {'usuarios': 5, 'activos': 50},
                'profesional': {'usuarios': 20, 'activos': 200},
                'empresarial': {'usuarios': 9999, 'activos': 99999},
            }

            # Verificamos si plan_seleccionado es una clave válida
            if plan_seleccionado not in limits:
                 # Esto no debería pasar si ChoiceField funciona, pero es una seguridad extra
                 raise serializers.ValidationError(f"Plan '{plan_seleccionado}' inválido seleccionado.")

            Suscripcion.objects.create(
                empresa=empresa,
                plan=plan_seleccionado, # Usar la variable validada
                estado='activa',
                fecha_inicio=timezone.now(),
                fecha_fin=timezone.now() + timedelta(days=30), # Suscripción de 30 días
                max_usuarios=limits[plan_seleccionado]['usuarios'],
                max_activos=limits[plan_seleccionado]['activos']
            )

            # 5. --- [NUEVO] Asignar Rol de Admin y Permisos por Defecto ---
            # Crear o obtener el rol 'Admin' para esta nueva empresa
            rol_admin, _ = Roles.objects.get_or_create(empresa=empresa, nombre='Admin')

            # Obtener todos los permisos excepto los de superadmin (si los hubiera)
            # Ajusta esto si quieres ser más específico
            permisos_para_admin = Permisos.objects.exclude(nombre__startswith='manage_permiso') # Excluir gestión global de permisos

            # Asignar todos esos permisos al rol 'Admin' de esta empresa
            rol_admin.permisos.set(permisos_para_admin)

            # Asignar el rol 'Admin' al nuevo empleado
            empleado.roles.add(rol_admin)
            # --- [FIN DE NUEVO CÓDIGO] ---

            return user # Devolvemos el usuario para generar el token

        except Exception as e:
             # Si algo falla (ej: error al crear suscripción, rol, etc.),
             # transaction.atomic deshará todo lo anterior.
             # Lanzamos un error de validación para que el frontend lo muestre.
             print(f"ERROR en RegisterEmpresaSerializer.create: {e}") # Log para el servidor
             raise serializers.ValidationError(f"Error interno durante el registro: {e}")

class EmpleadoSimpleSerializer(serializers.ModelSerializer):
    # Anidamos info básica del usuario
    usuario = UsuarioSerializer(read_only=True)
    class Meta:
        model = Empleado
        fields = ['id', 'usuario', 'apellido_p', 'apellido_m'] # Campos necesarios para mostrar nombre
        
class MantenimientoSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())    # Al LEER, anidamos info del activo y del empleado (read_only=True)
    activo = ActivoFijoSerializer(read_only=True)
    empleado_asignado = EmpleadoSimpleSerializer(read_only=True)

    # Al ESCRIBIR, esperamos solo los IDs (write_only=True)
    activo_id = serializers.PrimaryKeyRelatedField(
        queryset=ActivoFijo.objects.all(), source='activo', write_only=True
    )
    # Hacemos el ID del empleado opcional al escribir (required=False, allow_null=True)
    empleado_asignado_id = serializers.PrimaryKeyRelatedField(
        queryset=Empleado.objects.all(), source='empleado_asignado', write_only=True,
        required=False, allow_null=True
    )

    class Meta:
        model = Mantenimiento
        fields = [
            'id', 'tipo', 'estado', 'fecha_inicio', 'fecha_fin',
            'descripcion_problema', 'notas_solucion', 'costo',
            # Campos de lectura (anidados)
            'activo', 'empleado_asignado',
            # Campos de escritura (IDs)
            'activo_id', 'empleado_asignado_id',
            'empresa', # <-- AÑADIDO
        ]
        # La empresa se asigna automáticamente
        read_only_fields = () # <-- ELIMINADO read_only_fields

class OrdenesCompraSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    proveedor = ProveedorSerializer(read_only=True)
    solicitante = EmpleadoSimpleSerializer(read_only=True)

    proveedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Proveedor.objects.all(), source='proveedor', write_only=True
    )
    solicitante_id = serializers.PrimaryKeyRelatedField(
        queryset=Empleado.objects.all(), source='solicitante', write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = OrdenesCompra
        fields = [
            'id', 'estado', 'fecha_inicio', 'fecha_fin', 'condiciones', 'monto_total',
            'proveedor', 'solicitante', # Campos de lectura
            'proveedor_id', 'solicitante_id', 'empresa' # Campos de escritura
        ]

class ItemCatalogoSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    class Meta:
        model = ItemCatalogo
        fields = '__all__'

class InventarioSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())
    # Campos de Lectura (anidados)
    ubicacion = UbicacionSerializer(read_only=True)
    item_catalogo = ItemCatalogoSerializer(read_only=True)
    responsable = EmpleadoSimpleSerializer(read_only=True)

    # Campos de Escritura (IDs)
    ubicacion_id = serializers.PrimaryKeyRelatedField(
        queryset=Ubicacion.objects.all(), source='ubicacion', write_only=True
    )
    item_catalogo_id = serializers.PrimaryKeyRelatedField(
        queryset=ItemCatalogo.objects.all(), source='item_catalogo', write_only=True
    )
    responsable_id = serializers.PrimaryKeyRelatedField(
        queryset=Empleado.objects.all(), source='responsable', write_only=True, required=False, allow_null=True
    )
    detalle_compra_id = serializers.PrimaryKeyRelatedField(
        queryset=DetalleCompra.objects.all(), source='detalle_compra', write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Inventario
        fields = [
            'id', 'cantidad',
            'ubicacion', 'item_catalogo', 'responsable', # Lectura
            'ubicacion_id', 'item_catalogo_id', 'responsable_id', 'detalle_compra_id', 'empresa' # Escritura
        ]

class MovimientoInventarioSerializer(serializers.ModelSerializer):
    # No necesitamos anidar el inventario completo, con el ID es suficiente
    class Meta:
        model = MovimientoInventario
        fields = '__all__'

class ItemCatalogoSerializer(serializers.ModelSerializer):
    empresa = serializers.HiddenField(default=CurrentUserEmpresaDefault())

    class Meta:
        model = ItemCatalogo
        fields = '__all__'

class RevalorizacionActivoSerializer(serializers.ModelSerializer):
    activo = ActivoFijoSerializer(read_only=True)
    realizado_por = UsuarioSerializer(read_only=True)

    class Meta:
        model = RevalorizacionActivo
        fields = '__all__'

class SuscripcionSerializer(serializers.ModelSerializer):
    plan_display = serializers.CharField(source='get_plan_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    class Meta:
        model = Suscripcion
        fields = [
            'id', 'plan', 'estado', 'fecha_inicio', 'fecha_fin', 
            'max_usuarios', 'max_activos', 'plan_display', 'estado_display'
        ]
        read_only_fields = ('empresa',)

class NotificacionSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    
    class Meta:
        model = Notificacion
        fields = [
            'id', 'timestamp', 'mensaje', 'tipo', 'leido', 
            'url_destino', 'tipo_display'
        ]
        read_only_fields = ('empresa',)

class LogSerializer(serializers.ModelSerializer):
    # Definimos el usuario anidado para que se muestre info útil al LEER logs (opcional)
    # Al escribir, el backend lo asignará automáticamente.
    usuario = UsuarioSerializer(read_only=True)

    class Meta:
        model = Log
        fields = [
            'id',             # ID del log
            'timestamp',      # Fecha y hora (automático)
            'usuario',        # Info del usuario (automático)
            'ip_address',     # IP (automático)
            'tenant_id',      # ID Empresa (automático)
            'accion',         # Acción enviada por frontend (Requerido)
            'payload',        # Datos JSON enviados por frontend (Opcional)
        ]
        # Campos que el frontend NO debe enviar, los pone el backend
        read_only_fields = ('id', 'timestamp', 'usuario', 'ip_address', 'tenant_id')
        # Hacemos payload opcional al recibir datos
        extra_kwargs = {
            'accion': {'required': True},
            'payload': {'required': False, 'allow_null': True},
        }