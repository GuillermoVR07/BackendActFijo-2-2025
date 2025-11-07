# api/views.py
from rest_framework import viewsets, status, serializers
from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from .permissions import HasPermission, check_permission
import io
from django.http import HttpResponse, Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

from openpyxl import Workbook
from openpyxl.styles import Font
from .models import *
from .serializers import *
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
import logging
from django.db.models import Q
import re
from datetime import datetime
from django.db import transaction
from .report_utils import create_excel_report, create_pdf_report
from .filters import ActivoFijoFilter, ProveedorFilter, EmpleadoFilter, MantenimientoFilter, OrdenesCompraFilter, ItemCatalogoFilter, InventarioFilter, MovimientoInventarioFilter, PresupuestoFilter, UbicacionFilter, EstadoFilter # <-- NUEVA IMPORTACIÓN
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal, InvalidOperation
logger = logging.getLogger(__name__)

class MyThemePreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request):
        # SOLO devuelve empleado si NO es staff
        if not request.user.is_staff:
            try:
                return request.user.empleado
            except Empleado.DoesNotExist:
                # Usuario normal sin perfil, esto es un error de datos
                raise serializers.ValidationError("Usuario no asociado a un perfil de empleado.")
        # Si es staff (SuperAdmin), devuelve None
        return None

    def get(self, request, *args, **kwargs):
        """Devuelve preferencias del empleado o defaults para SuperAdmin."""
        empleado = self.get_object(request) # Puede ser None si es SuperAdmin

        if empleado:
            data = {
                'theme_preference': empleado.theme_preference,
                'theme_custom_color': empleado.theme_custom_color,
                'theme_glow_enabled': empleado.theme_glow_enabled,
            }
        else:
            # Valores por defecto para SuperAdmin (o si falla get_object)
            data = {
                'theme_preference': 'dark',
                'theme_custom_color': '#6366F1',
                'theme_glow_enabled': False,
            }
        return Response(data, status=status.HTTP_200_OK)


    def patch(self, request, *args, **kwargs):
        """Actualiza preferencias SOLO para empleados normales."""
        empleado = self.get_object(request)

        # Si es SuperAdmin (empleado es None), prohibir guardar
        if empleado is None:
            return Response(
                {"detail": "El SuperAdmin no tiene preferencias de tema guardadas."},
                status=status.HTTP_403_FORBIDDEN # 403 Prohibido
            )

        # --- Lógica de validación y guardado (sin cambios) ---
        try:
            allowed_fields = ['theme_preference', 'theme_custom_color', 'theme_glow_enabled']
            update_data = {}
            valid = True
            errors = {}
            fields_to_update = [] # Lista para guardar solo los campos que llegaron

            for field in allowed_fields:
                if field in request.data:
                    value = request.data[field]
                    fields_to_update.append(field) # Añadir a la lista para .save()
                    # (Validaciones básicas...)
                    if field == 'theme_preference' and value not in ['light', 'dark', 'custom', None, '']:
                         valid = False; errors[field] = "Valor inválido."
                    elif field == 'theme_custom_color' and value is not None and value != '' and not (isinstance(value, str) and value.startswith('#') and len(value) in [4, 7]):
                         valid = False; errors[field] = "Formato de color inválido."
                    elif field == 'theme_glow_enabled' and not isinstance(value, bool):
                         valid = False; errors[field] = "Debe ser booleano."

                    if valid:
                        setattr(empleado, field, value)

            if not valid:
                 return Response(errors, status=status.HTTP_400_BAD_REQUEST)

            # Guardar solo los campos que se enviaron en el PATCH
            if fields_to_update:
                 empleado.save(update_fields=fields_to_update)

            updated_data = {
                'theme_preference': empleado.theme_preference,
                'theme_custom_color': empleado.theme_custom_color,
                'theme_glow_enabled': empleado.theme_glow_enabled,
            }
            return Response(updated_data, status=status.HTTP_200_OK)

        except serializers.ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
             print(f"ERROR en MyThemePreferencesView.patch: {e}")
             return Response({"detail": "Error interno."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)        
        
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

# --- VIEWSET BASE PARA LÓGICA MULTI-TENANT ---
#class BaseTenantViewSet(viewsets.ModelViewSet):
#    permission_classes = [IsAuthenticated]
#
#    def get_queryset(self):
#        try:
#            empleado = self.request.user.empleado
#            return self.queryset.filter(empresa=empleado.empresa)
#        except Empleado.DoesNotExist:
#            return self.queryset.none()
#
#    def perform_create(self, serializer):
#        empleado = self.request.user.empleado
#        serializer.save(empresa=empleado.empresa)

class BaseTenantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Modificado para que el Superusuario (is_staff) pueda ver
        TODOS los objetos, sin filtrar por empresa.
        """
        # 1. Si el usuario es staff (Superusuario), saltar el filtro de tenant
        if self.request.user.is_staff:
            print(f"DEBUG: get_queryset for SUPERUSER: {self.request.user}. Returning all objects.")
            return self.queryset.all() # <-- Devuelve todo

        # 2. Si es un usuario normal, aplicar el filtro de tenant
        try:
            print(f"DEBUG: get_queryset called by user: {self.request.user}")
            empleado = self.request.user.empleado
            print(f"DEBUG: Found empleado: {empleado}, for empresa: {empleado.empresa}")
            
            queryset = self.queryset.filter(empresa=empleado.empresa)
            print(f"DEBUG: Filtered queryset count: {queryset.count()}")
            return queryset
        except Empleado.DoesNotExist:
            print(f"DEBUG: Empleado.DoesNotExist for user: {self.request.user}")
            return self.queryset.none()
        except Exception as e:
             print(f"ERROR in get_queryset: {e}")
             return self.queryset.none()       

    def check_permissions(self, request):
        super().check_permissions(request) 
        required_permission = getattr(self, 'required_manage_permission', None)
        if required_permission and request.method not in permissions.SAFE_METHODS:
             if not check_permission(request, self, required_permission):
                 self.permission_denied(
                     request, message=f'Permiso "{required_permission}" requerido.'
                 )
    
class BaseTenantLimitViewSet(BaseTenantViewSet):
    """
    ViewSet que comprueba los límites de la suscripción antes de CUALQUIER
    creación (POST) de un nuevo objeto (ej. Empleado o ActivoFijo).
    """
    model_to_count = None       # Ej: Empleado
    model_limit_field = None  # Ej: 'max_usuarios'

    def create(self, request, *args, **kwargs):
        empleado = request.user.empleado
        empresa = empleado.empresa

        if self.model_to_count and self.model_limit_field:
            try:
                suscripcion = empresa.suscripcion
                
                # 1. Comprobar si la suscripción está activa
                if suscripcion.estado != 'activa':
                    return Response(
                        {'detail': 'Tu suscripción no está activa. No puedes añadir nuevos registros.'},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # 2. Comprobar límite
                current_count = self.model_to_count.objects.filter(empresa=empresa).count()
                limit = getattr(suscripcion, self.model_limit_field)

                if current_count >= limit:
                    # Límite alcanzado, bloquear creación
                    return Response(
                        {'detail': f'Has alcanzado el límite de {limit} {self.model_to_count._meta.verbose_name_plural} '
                                   f'para tu plan {suscripcion.get_plan_display()}. Por favor, actualiza tu plan.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # 3. Comprobar umbral de notificación (90%) y crear notificación
                # (Se comprueba ANTES de crear, para notificar en el 90%)
                threshold = limit * 0.9
                if (current_count + 1) > threshold and limit < 9999: # No notificar si es "ilimitado"
                    # Usamos get_or_create para no spamear notificaciones idénticas
                    Notificacion.objects.get_or_create(
                        empresa=empresa,
                        leido=False,
                        tipo='ADVERTENCIA',
                        mensaje=f'Estás cerca de tu límite de {self.model_to_count._meta.verbose_name_plural}. '
                                f'Uso actual: {current_count + 1} de {limit}.'
                        ,
                        defaults={'url_destino': '/app/suscripcion'} # URL en el frontend
                    )
            
            except Suscripcion.DoesNotExist:
                return Response(
                    {'detail': 'Error: No se encontró una suscripción para tu empresa.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'detail': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Si todo está bien (o no hay límites definidos), procede con la creación normal
        return super().create(request, *args, **kwargs)
    
class CargoViewSet(BaseTenantViewSet):
    queryset = Cargo.objects.all()
    serializer_class = CargoSerializer
    required_manage_permission = 'manage_cargo'

class DepartamentoViewSet(BaseTenantViewSet):
    queryset = Departamento.objects.all()
    serializer_class = DepartamentoSerializer
    required_manage_permission = 'manage_departamento'

#class EmpleadoViewSet(BaseTenantViewSet):
#    queryset = Empleado.objects.all()
#    serializer_class = EmpleadoSerializer
#
#    # --- AÑADE ESTE MÉTODO ---
#    def create(self, request, *args, **kwargs):
#        """
#        Sobrescribe el método create para devolver una respuesta simple.
#        """
#        serializer = self.get_serializer(data=request.data)
#        serializer.is_valid(raise_exception=True)
#        # perform_create asigna la empresa automáticamente
#        self.perform_create(serializer) 
#        
#        # En lugar de devolver serializer.data (que puede fallar),
#        # devolvemos solo el ID y un mensaje.
#        headers = self.get_success_headers(serializer.data)
#        return Response(
#            {"id": serializer.instance.id, "detail": "Empleado creado con éxito."}, 
#            status=status.HTTP_201_CREATED, 
#            headers=headers
#        )

#class EmpleadoViewSet(BaseTenantViewSet):
#    queryset = Empleado.objects.all().select_related('usuario', 'cargo', 'departamento').prefetch_related('roles') # Optimization
#    serializer_class = EmpleadoSerializer
#    required_manage_permission = 'manage_empleado'
#
#    def create(self, request, *args, **kwargs):
#        # ... (Your existing create method returning simple response)
#        # Ensure perform_create is called correctly within this method if you override it
#        serializer = self.get_serializer(data=request.data)
#        serializer.is_valid(raise_exception=True)
#        self.perform_create(serializer) # Make sure this line exists and is called
#        headers = self.get_success_headers(serializer.data)
#        # Ensure serializer.instance is available AFTER perform_create
#        if hasattr(serializer, 'instance'):
#             return Response(
#                 {"id": serializer.instance.id, "detail": "Empleado creado con éxito."},
#                 status=status.HTTP_201_CREATED,
#                 headers=headers
#            )
#        else: # Should not happen if perform_create works
#             print("ERROR: serializer.instance not found after perform_create")
#             return Response({"detail":"Error creating employee instance."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmpleadoViewSet(BaseTenantLimitViewSet):
    queryset = Empleado.objects.all().select_related('usuario', 'cargo', 'departamento').prefetch_related('roles')
    serializer_class = EmpleadoSerializer
    required_manage_permission = 'manage_empleado'
    
    # --- [NUEVO] Definir los campos para el chequeo de límites ---
    model_to_count = Empleado
    model_limit_field = 'max_usuarios'

    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = EmpleadoFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['usuario__first_name', 'apellido_p', 'apellido_m', 'ci', 'usuario__email']

class ActivoFijoViewSet(BaseTenantViewSet):
    queryset = ActivoFijo.objects.all()
    serializer_class = ActivoFijoSerializer
    required_manage_permission = 'manage_activofijo'

    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    # Usa la clase de filtro personalizado que creamos en api/filters.py
    filterset_class = ActivoFijoFilter
    # Añade el backend de Búsqueda general de DRF
    filter_backends = (DjangoFilterBackend, SearchFilter)
    # Define los campos sobre los que actuará el parámetro ?search=
    search_fields = ['nombre', 'codigo_interno', 'serial']

class PresupuestoViewSet(BaseTenantViewSet):
    queryset = Presupuesto.objects.all()
    serializer_class = PresupuestoSerializer
    required_manage_permission = 'manage_presupuesto'

    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = PresupuestoFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['descripcion', 'departamento__nombre']

    def get_queryset(self):
        """
        Sobrescribe el método base para filtrar a través del departamento.
        """
        if self.request.user.is_staff:
            return self.queryset.all()
        
        try:
            empleado = self.request.user.empleado
            return self.queryset.filter(departamento__empresa=empleado.empresa)
        except Empleado.DoesNotExist:
            return self.queryset.none()

    def perform_create(self, serializer):
        """
        Sobrescribe el método base para guardar sin inyectar la empresa,
        ya que el modelo Presupuesto no tiene el campo 'empresa'.
        La validación del departamento asegura que pertenece a la empresa correcta.
        """
        # Validar que el departamento pertenezca a la empresa del usuario
        departamento = serializer.validated_data.get('departamento')
        if departamento.empresa != self.request.user.empleado.empresa:
            raise serializers.ValidationError({
                "departamento_id": "Este departamento no pertenece a tu empresa."
            })
        serializer.save()

class RolesViewSet(BaseTenantViewSet):
    queryset = Roles.objects.all()
    serializer_class = RolesSerializer
    required_manage_permission = 'manage_rol'

class EstadoViewSet(BaseTenantViewSet):
    queryset = Estado.objects.all()
    serializer_class = EstadoSerializer
    required_manage_permission = 'manage_estadoactivo'
    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = EstadoFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['nombre']

class UbicacionViewSet(BaseTenantViewSet):
    queryset = Ubicacion.objects.all()
    serializer_class = UbicacionSerializer
    required_manage_permission = 'manage_ubicacion'
    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = UbicacionFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['nombre', 'direccion']

class ProveedorViewSet(BaseTenantViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    required_manage_permission = 'manage_proveedor'

    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = ProveedorFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['nombre', 'nit', 'email']

class PermisosViewSet(viewsets.ModelViewSet): 
    """
    ViewSet para gestionar los Permisos Globales...
    """
    queryset = Permisos.objects.all().order_by('nombre')
    serializer_class = PermisosSerializer
    
    def get_permissions(self):
        # ... (permission logic) ...
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        # Requiere ser Superusuario (is_staff=True) para otras acciones (POST, PUT, DELETE)
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

class LogViewSet(viewsets.ModelViewSet):
    """
    ViewSet para recibir y guardar registros de log desde el frontend.
    No usa el filtro de tenant porque es una función a nivel de sistema.
    """
    queryset = Log.objects.all()
    serializer_class = LogSerializer
    permission_classes = [IsAuthenticated] # Solo usuarios autenticados pueden registrar logs

    def perform_create(self, serializer):
        # Obtenemos la IP del cliente de forma segura
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')

        # Asignamos los datos automáticos antes de guardar
        empleado = self.request.user.empleado
        serializer.save(
            usuario=self.request.user,
            ip_address=ip,
            tenant_id=empleado.empresa.id if empleado else None
        )

class RegisterEmpresaView(APIView):
    permission_classes = [AllowAny] 

    def post(self, request, *args, **kwargs):
        # Usamos el parser de Form data para aceptar 'plan' y 'fotos'
        serializer = RegisterEmpresaSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()                         
            refresh = RefreshToken.for_user(user)
            token = refresh.access_token
            
            # Repoblamos el token con los datos (serializer.save() devuelve el user)
            try:
                empleado = user.empleado
                token['username'] = user.username
                token['email'] = user.email
                token['nombre_completo'] = f"{user.first_name} {empleado.apellido_p}"
                token['empresa_id'] = str(empleado.empresa.id)
                token['empresa_nombre'] = empleado.empresa.nombre
                token['empleado_id'] = str(empleado.id)
                # Al registrarse, el rol de Admin aún no está asignado (a menos que lo hagas en el serializer)
                token['roles'] = [] # Vacío por ahora
                token['is_admin'] = user.is_staff
            except Empleado.DoesNotExist:
                token['roles'] = []
                token['is_admin'] = user.is_staff
                
            return Response({
                'refresh': str(refresh),
                'access': str(token),
            }, status=status.HTTP_201_CREATED) # type: ignore
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserPermissionsView(APIView):
    # (Tu vista de permisos está bien)
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        permissions_set = set()
        try:
            empleado = request.user.empleado
            permissions_set = set(
                empleado.roles.values_list('permisos__nombre', flat=True).distinct()
            )
            if request.user.is_staff:
                 permissions_set.add('is_superuser')
        except Empleado.DoesNotExist:
            if request.user.is_staff:
                 permissions_set.add('is_superuser')
            pass 
        except Exception as e:
            print(f"Error fetching user permissions: {e}")
        return Response(list(permissions_set))

class ReporteActivosPreview(APIView):
    """
    Vista previa para el reporte original basado en filtros de formulario.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        empleado = request.user.empleado
        queryset = ActivoFijo.objects.filter(empresa=empleado.empresa).select_related(
            'item_catalogo', 'estado', 'ubicacion', 'departamento' # Asegurar todos los relateds
        )
        ubicacion_id = request.query_params.get('ubicacion_id') 
        fecha_min = request.query_params.get('fecha_min')
        fecha_max = request.query_params.get('fecha_max')
        
        # Aplicar filtros
        if ubicacion_id:
            queryset = queryset.filter(ubicacion_id=ubicacion_id)
        if fecha_min:
            queryset = queryset.filter(fecha_adquisicion__gte=fecha_min)
        if fecha_max:
            queryset = queryset.filter(fecha_adquisicion__lte=fecha_max)
            
        return queryset.order_by('fecha_adquisicion')

    def get(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset(request)
            # Devolver los campos que el frontend necesita para la tabla
            data = queryset.values(
                'id', 'nombre', 'codigo_interno', 'fecha_adquisicion', 'valor_actual',
                'ubicacion__nombre', 'item_catalogo__nombre', 'departamento__nombre'
            )
            return Response(list(data))
        except Empleado.DoesNotExist:
             return Response({"detail": "Usuario no asociado a un empleado."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
             logger.error(f"ReporteActivosPreview Error: {e}", exc_info=True)
             return Response({"detail": "Error al generar vista previa."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReporteActivosExport(APIView):
    """
    Exporta el reporte original (filtros de formulario) a PDF o Excel.
    Reutiliza funciones de report_utils.py
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        try:
            # Reutiliza la lógica de get_queryset de la vista previa
            # y asegura que todos los campos relacionados necesarios estén
            qs = ReporteActivosPreview().get_queryset(request).select_related(
               'ubicacion', 'estado', 'item_catalogo', 'departamento'
            )
            logger.info(f"Report Export: Queryset count = {qs.count()}")
            return qs
        except Exception as e:
            logger.error(f"Report Export: Error in get_queryset: {e}", exc_info=True)
            raise Http404("Error al obtener datos base.")

    def get(self, request, *args, **kwargs):
        export_format = request.query_params.get('format', 'pdf').lower()
        logger.info(f"Report Export GET request. Format = {export_format}")
        try:
            queryset = self.get_queryset(request)
            if not queryset.exists():
                 logger.warning("Report Export: Queryset is empty.")
                 return Response({"detail": "No hay datos para exportar con esos filtros."}, status=status.HTTP_404_NOT_FOUND)

            # --- Llamar a funciones de utils ---
            if export_format == 'excel':
                logger.info("Report Export: Calling create_excel_report util...")
                response = create_excel_report(queryset)
                logger.info("Report Export: create_excel_report finished.")
                return response
            else:
                logger.info("Report Export: Calling create_pdf_report util...")
                response = create_pdf_report(queryset)
                logger.info("Report Export: create_pdf_report finished.")
                return response

        except Http404 as e:
             logger.warning(f"Report Export: Http404 raised - {e}")
             return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
             logger.error(f"Report Export: Unhandled error in GET: {e}", exc_info=True)
             return Response({"detail": f"Error interno al generar el reporte: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # --- FUNCIÓN HELPER PARA REPORTE DINÁMICO ---
    def parse_and_build_query(filters_list, base_queryset):
        """
        Toma una lista de strings de filtro (ej: ["depto:TI", "laptop", "valor>500"])
        y la convierte en un queryset de Django filtrado.
        """
        query = base_queryset
        
        # Mapeo de claves a campos base del modelo ActivoFijo
        field_mapping = {
            'depto': 'departamento__nombre',
            'categoria': 'item_catalogo__nombre',
            'ubicacion': 'ubicacion__nombre',
            'estado': 'estado__nombre',
            'proveedor': 'proveedor__nombre',
            'nombre': 'nombre',
            'codigo': 'codigo_interno',
            'valor': 'valor_actual',
            'fecha_adq': 'fecha_adquisicion',
        }

        # Mapeo de operadores de texto/numéricos a suffixes de Django ORM
        operator_mapping = {
            ':': '__icontains', # Búsqueda de texto flexible (contiene, sin mayúsculas)
            '>': '__gt',        # Mayor que
            '<': '__lt',        # Menor que
            '=': '__exact',     # Coincidencia exacta
        }

        q_objects = Q() # Inicializa un objeto Q vacío (para combinar filtros con AND)

        for f in filters_list:
            try:
                f = f.strip()
                if not f: continue # Ignorar filtros vacíos

                # --- NUEVA LÓGICA DE PARSEO ---
                # Intenta encontrar un patrón como "clave:valor", "clave>valor", "clave < valor"
                # Regex: (clave) (espacios) (operador) (espacios) (valor)
                match = re.match(r'([\w_]+)\s*([:<>])\s*(.+)', f)
                
                if match:
                    # --- Filtro Estructurado (ej: "depto: TI", "valor > 1000") ---
                    key, operator, value = match.groups()
                    key = key.lower().strip()
                    operator = operator.strip()
                    value = value.strip()
                    
                    # Verificar si la clave y el operador son válidos
                    if key in field_mapping and operator in operator_mapping:
                        # Construir el nombre completo del campo ORM (ej: 'valor_actual__gt')
                        orm_field = field_mapping[key] + operator_mapping[operator]
                        
                        # Convertir valor si es numérico o fecha
                        if operator in ['>', '<', '='] and key in ['valor', 'fecha_adq']:
                            try:
                                if key == 'valor':
                                    value = float(value) # Convertir a número
                                elif key == 'fecha_adq':
                                    # Asumir formato YYYY-MM-DD
                                    value = datetime.strptime(value, '%Y-%m-%d').date()
                            except ValueError:
                                logger.warn(f"Filtro ignorado: Valor para '{key}{operator}' no es válido: '{value}'")
                                continue # Saltar este filtro
                        
                        # Añadir al query (ej: Q(valor_actual__gt=1000))
                        q_objects &= Q(**{orm_field: value})
                    else:
                        logger.warn(f"Filtro ignorado: Clave '{key}' u operador '{operator}' no reconocidos.")

                # --- Filtro de Texto Simple (ej: "laptop", "finanzas") ---
                else:
                    # Si no es un filtro estructurado, buscar el texto en MÚLTIPLES campos
                    q_objects &= (
                        Q(nombre__icontains=f) | 
                        Q(codigo_interno__icontains=f) |
                        Q(departamento__nombre__icontains=f) |
                        Q(item_catalogo__nombre__icontains=f) |
                        Q(ubicacion__nombre__icontains=f) |
                        Q(estado__nombre__icontains=f) |
                        Q(proveedor__nombre__icontains=f)
                    )
            except Exception as e:
                # Ignorar filtros malformados (ej: "valor>abc")
                logger.warn(f"Report Query: Ignorando filtro malformado: '{f}'. Error: {e}")
                pass
                
        # Aplicar todos los filtros combinados (Q objects) al queryset
        return query.filter(q_objects).distinct()

class ReporteQueryView(APIView):
    """
    Recibe filtros dinámicos (POST) y devuelve una vista previa JSON.
    Endpoint: /api/reportes/query/
    """
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self, request):
        # Filtrar por tenant (empresa)
        try:
            empleado = request.user.empleado
            # Precargar todos los campos relacionados que podamos necesitar
            return ActivoFijo.objects.filter(empresa=empleado.empresa).select_related(
                'departamento', 'ubicacion', 'item_catalogo', 'estado', 'proveedor'
            )
        except Empleado.DoesNotExist:
            if request.user.is_staff:
                 return ActivoFijo.objects.all().select_related(
                    'departamento', 'ubicacion', 'item_catalogo', 'estado', 'proveedor'
                 )
            return ActivoFijo.objects.none()

    def post(self, request, *args, **kwargs):
        filters = request.data.get('filters', [])
        if not isinstance(filters, list):
             return Response({"detail": "El campo 'filters' debe ser una lista."}, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Report Query Preview POST. Filters = {filters}")
        try:
            base_qs = self.get_base_queryset(request)
            queryset = ReporteQueryView.parse_and_build_query(filters, base_qs)
            
            # Devolver los datos que el frontend espera en la tabla
            data = queryset.values(
                'id', 'nombre', 'codigo_interno', 'fecha_adquisicion', 'valor_actual',
                'departamento__nombre',
                'ubicacion__nombre'
            )
            return Response(list(data), status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Report Query Error: {e}", exc_info=True)
            return Response({"detail": f"Error al procesar la consulta: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def parse_and_build_query(filters_list, base_queryset):
        """
        Toma una lista de strings de filtro (ej: ["depto:TI", "laptop", "valor>500"])
        y la convierte en un queryset de Django filtrado.
        """
        query = base_queryset
        
        # Mapeo de claves a campos base del modelo ActivoFijo
        field_mapping = {
            'depto': 'departamento__nombre',
            'categoria': 'item_catalogo__nombre',
            'ubicacion': 'ubicacion__nombre',
            'estado': 'estado__nombre',
            'proveedor': 'proveedor__nombre',
            'nombre': 'nombre',
            'codigo': 'codigo_interno',
            'valor': 'valor_actual',
            'fecha_adq': 'fecha_adquisicion',
        }

        # Mapeo de operadores de texto/numéricos a suffixes de Django ORM
        operator_mapping = {
            ':': '__icontains', # Búsqueda de texto flexible (contiene, sin mayúsculas)
            '>': '__gt',        # Mayor que
            '<': '__lt',        # Menor que
            '=': '__exact',     # Coincidencia exacta
        }

        q_objects = Q() # Inicializa un objeto Q vacío (para combinar filtros con AND)

        for f in filters_list:
            try:
                f = f.strip()
                if not f: continue # Ignorar filtros vacíos

                # --- NUEVA LÓGICA DE PARSEO ---
                # Intenta encontrar un patrón como "clave:valor", "clave>valor", "clave < valor"
                # Regex: (clave) (espacios) (operador) (espacios) (valor)
                match = re.match(r'([\w_]+)\s*([:<>])\s*(.+)', f)
                
                if match:
                    # --- Filtro Estructurado (ej: "depto: TI", "valor > 1000") ---
                    key, operator, value = match.groups()
                    key = key.lower().strip()
                    operator = operator.strip()
                    value = value.strip()
                    
                    # Verificar si la clave y el operador son válidos
                    if key in field_mapping and operator in operator_mapping:
                        # Construir el nombre completo del campo ORM (ej: 'valor_actual__gt')
                        orm_field = field_mapping[key] + operator_mapping[operator]
                        
                        # Convertir valor si es numérico o fecha
                        if operator in ['>', '<', '='] and key in ['valor', 'fecha_adq']:
                            try:
                                if key == 'valor':
                                    value = float(value) # Convertir a número
                                elif key == 'fecha_adq':
                                    # Asumir formato YYYY-MM-DD
                                    value = datetime.strptime(value, '%Y-%m-%d').date()
                            except ValueError:
                                logger.warn(f"Filtro ignorado: Valor para '{key}{operator}' no es válido: '{value}'")
                                continue # Saltar este filtro
                        
                        # Añadir al query (ej: Q(valor_actual__gt=1000))
                        q_objects &= Q(**{orm_field: value})
                    else:
                        logger.warn(f"Filtro ignorado: Clave '{key}' u operador '{operator}' no reconocidos.")

                # --- Filtro de Texto Simple (ej: "laptop", "finanzas") ---
                else:
                    # Si no es un filtro estructurado, buscar el texto en MÚLTIPLES campos
                    q_objects &= (
                        Q(nombre__icontains=f) | 
                        Q(codigo_interno__icontains=f) |
                        Q(departamento__nombre__icontains=f) |
                        Q(categoria__nombre__icontains=f) |
                        Q(ubicacion__nombre__icontains=f) |
                        Q(estado__nombre__icontains=f) |
                        Q(proveedor__nombre__icontains=f)
                    )
            except Exception as e:
                # Ignorar filtros malformados (ej: "valor>abc")
                logger.warn(f"Report Query: Ignorando filtro malformado: '{f}'. Error: {e}")
                pass
                
        # Aplicar todos los filtros combinados (Q objects) al queryset
        return query.filter(q_objects).distinct()

class ReporteQueryExportView(ReporteQueryView):
    """
    Recibe filtros dinámicos y formato (POST) y devuelve un archivo PDF/Excel
    usando las funciones de report_utils.py
    """
    
    def post(self, request, *args, **kwargs):
        filters = request.data.get('filters', [])
        export_format = request.data.get('format', 'pdf').lower()
        
        if not isinstance(filters, list):
             return Response({"detail": "Filters debe ser lista."}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Report Query Export POST. Format = {export_format}, Filters = {filters}")
        try:
            # Obtener queryset base (ya tiene select_related)
            base_qs = self.get_base_queryset(request)
            # Aplicar filtros
            queryset = ReporteQueryView.parse_and_build_query(filters, base_qs)

            if not queryset.exists():
                logger.warning("Report Query Export: Queryset is empty.")
                return Response({"detail": "No hay datos para exportar."}, status=status.HTTP_404_NOT_FOUND)

            # --- Llamar a funciones de utils ---
            if export_format == 'excel':
                logger.info("Report Query Export: Calling create_excel_report util...")
                return create_excel_report(queryset) # <-- LLAMADA A UTIL
            else:
                logger.info("Report Query Export: Calling create_pdf_report util...")
                return create_pdf_report(queryset) # <-- LLAMADA A UTIL

        except Http404 as e:
            logger.warning(f"Report Query Export: Http404 - {e}")
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Report Query Export Error: {e}", exc_info=True)
            return Response({"detail": f"Error al exportar: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
class MantenimientoViewSet(BaseTenantViewSet):
    queryset = Mantenimiento.objects.all().select_related('activo', 'empleado_asignado__usuario') # Optimizar query
    serializer_class = MantenimientoSerializer
    required_manage_permission = 'manage_mantenimiento'

    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = MantenimientoFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['activo__nombre', 'activo__codigo_interno', 'descripcion_problema', 'notas_solucion']

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated]) # No necesita permiso especial aquí, validamos adentro
    def actualizar_estado(self, request, pk=None):
        """
        Permite al empleado asignado actualizar estado, notas y (opcional) foto.
        """
        try:
            mantenimiento = self.get_object() # Obtiene el mantenimiento por ID (pk)
            empleado_actual = request.user.empleado

            # 1. Verificar si el usuario es el empleado asignado
            if mantenimiento.empleado_asignado != empleado_actual:
                # Opcional: Permitir si tiene manage_mantenimiento también? Por ahora no.
                # checker = HasPermission('manage_mantenimiento')
                # if not checker.has_object_permission(request, self, mantenimiento):
                 return Response({'detail': 'No tienes permiso para actualizar este mantenimiento.'},
                                status=status.HTTP_403_FORBIDDEN)

            # 2. Validar y actualizar solo los campos permitidos
            # Usamos un serializer simple o validación manual
            allowed_updates = {}
            valid = True
            errors = {}

            if 'estado' in request.data:
                nuevo_estado = request.data['estado']
                if nuevo_estado not in dict(Mantenimiento.ESTADO_CHOICES).keys():
                    valid = False; errors['estado'] = 'Estado inválido.'
                else:
                    allowed_updates['estado'] = nuevo_estado

            if 'notas_solucion' in request.data:
                allowed_updates['notas_solucion'] = request.data['notas_solucion']

            # Aquí podrías añadir lógica para 'foto_evidencia' si la añades al modelo

            if not valid:
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)

            # Actualizar campos y guardar
            for field, value in allowed_updates.items():
                setattr(mantenimiento, field, value)

            # Marcar fecha_fin si el estado es COMPLETADO
            if allowed_updates.get('estado') == 'COMPLETADO' and not mantenimiento.fecha_fin:
                 mantenimiento.fecha_fin = timezone.now() # O usar django.utils.timezone
                 allowed_updates['fecha_fin'] = mantenimiento.fecha_fin # Añadir al log

            if allowed_updates:
                 mantenimiento.save(update_fields=allowed_updates.keys())

                 # (Opcional) Crear notificación para el Admin que lo creó/asignó?
                 # ... Lógica para encontrar al admin y crear Notificacion ...

                 # Loguear la acción específica
                 logAction(f'UPDATE_STATUS: Mantenimiento por {empleado_actual.usuario.username}', {'id': pk, **allowed_updates})


            # Devolver el objeto actualizado (o solo un success)
            serializer = self.get_serializer(mantenimiento)
            return Response(serializer.data, status=status.HTTP_200_OK)


        except Empleado.DoesNotExist:
             return Response({'detail': 'Perfil de empleado no encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
        except Mantenimiento.DoesNotExist:
             return Response({'detail': 'Mantenimiento no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"ERROR en actualizar_estado: {e}")
            return Response({'detail': f'Error interno: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    # --- [NUEVA FUNCIÓN HELPER] ---
    def _crear_notificacion_asignacion(self, mantenimiento_instance):
        empleado_asignado = mantenimiento_instance.empleado_asignado
        # --- [CAMBIO] Verificar que el empleado tenga usuario ---
        if empleado_asignado and hasattr(empleado_asignado, 'usuario'):
            destinatario_user = empleado_asignado.usuario
            try:
                mensaje = (f"Se te ha asignado una tarea de mantenimiento ({mantenimiento_instance.get_tipo_display()}) "
                           f"para el activo '{mantenimiento_instance.activo.nombre}'.")

                # --- [CAMBIO] Crear notificación para el USUARIO destinatario ---
                Notificacion.objects.create(
                    destinatario=destinatario_user, # <-- ASIGNAR A USER
                    mensaje=mensaje,
                    tipo='INFO',
                )
                print(f"DEBUG: Notificación de asignación creada para usuario {destinatario_user.id}")
            except Exception as e:
                print(f"ERROR: No se pudo crear notificación para mant. {mantenimiento_instance.id}. Error: {e}")
        elif empleado_asignado:
             print(f"WARN: Empleado {empleado_asignado.id} asignado a mant. {mantenimiento_instance.id} no tiene usuario asociado.")

    # --- [ MÉTODO EDITADO ] ---
    def perform_create(self, serializer):
        # Primero, guarda el mantenimiento normalmente (asignando la empresa del usuario creador)
        empleado_creador = self.request.user.empleado
        mantenimiento = serializer.save(empresa=self.request.user.empleado.empresa)
        # Luego, intenta crear la notificación para el asignado (si existe)
        self._crear_notificacion_asignacion(mantenimiento)

    # --- [ MÉTODO EDITADO ] ---
    def perform_update(self, serializer):
        # Guarda la actualización normalmente
        mantenimiento = serializer.save()
        # Comprueba si el empleado asignado cambió o si se asignó uno nuevo
        # (Podrías hacer una lógica más compleja para notificar solo si cambia la asignación)
        # Por simplicidad, notificamos siempre que haya alguien asignado tras guardar.
        self._crear_notificacion_asignacion(mantenimiento)

class OrdenesCompraViewSet(BaseTenantViewSet):
    queryset = OrdenesCompra.objects.all().select_related('proveedor', 'solicitante__usuario')
    serializer_class = OrdenesCompraSerializer
    required_manage_permission = 'manage_orden_compra' # Necesitarás crear este permiso

class ItemCatalogoViewSet(BaseTenantViewSet):
    queryset = ItemCatalogo.objects.all()
    serializer_class = ItemCatalogoSerializer
    required_manage_permission = 'manage_item_catalogo' # Necesitarás crear este permiso

    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = OrdenesCompraFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['id', 'proveedor__nombre', 'solicitante__usuario__first_name', 'condiciones']

class RevalorizacionActivoViewSet(BaseTenantViewSet):
    queryset = RevalorizacionActivo.objects.all()
    serializer_class = RevalorizacionActivoSerializer
    required_manage_permission = 'manage_revalorizacion'

    def get_queryset(self):
        qs = super().get_queryset()
        activo_id = self.request.query_params.get('activo_id')
        if activo_id:
            return qs.filter(activo_id=activo_id)
        return qs

    @action(detail=False, methods=['post'], url_path='ejecutar')
    def ejecutar(self, request, *args, **kwargs):
        # 1. Comprobar permiso explícitamente para esta acción
        if not check_permission(request, self, self.required_manage_permission):
            self.permission_denied(request, message=f'Permiso "{self.required_manage_permission}" requerido.')

        # 2. Validar datos de entrada
        activo_id = request.data.get('activo_id')
        reval_type = request.data.get('reval_type') # 'factor', 'fijo', 'porcentual'
        value_str = request.data.get('value')
        notas = request.data.get('notas')

        if not all([activo_id, reval_type, value_str]):
            return Response({'detail': 'Se requieren activo_id, reval_type y value.'}, status=status.HTTP_400_BAD_REQUEST)

        if reval_type not in ['factor', 'fijo', 'porcentual']:
            return Response({'detail': 'reval_type inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            value = Decimal(value_str)
            if reval_type == 'porcentual':
                if value <= -100:
                    raise ValueError("El porcentaje no puede ser menor o igual a -100%.")
            elif value < 0:
                raise ValueError("El valor no puede ser negativo para este método.")

        except (ValueError, InvalidOperation) as e:
            return Response({'detail': str(e) or 'El valor proporcionado no es un número válido.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Determinar la empresa del usuario
                empresa_obj = Empresa.objects.first() if request.user.is_staff else request.user.empleado.empresa
                if not empresa_obj:
                    return Response({'detail': 'No se pudo determinar la empresa para la operación.'}, status=status.HTTP_400_BAD_REQUEST)

                activo = ActivoFijo.objects.select_for_update().get(
                    id=activo_id, 
                    empresa=empresa_obj
                )

                valor_anterior = activo.valor_actual
                valor_nuevo = Decimal(0)
                factor_aplicado = Decimal(1)

                if valor_anterior == 0 and reval_type != 'fijo':
                    return Response({'detail': 'No se puede revalorizar por factor o porcentaje un activo con valor cero.'}, status=status.HTTP_400_BAD_REQUEST)

                # 3. Calcular el nuevo valor según el tipo
                if reval_type == 'factor':
                    factor_aplicado = value
                    valor_nuevo = valor_anterior * factor_aplicado
                elif reval_type == 'fijo':
                    valor_nuevo = value
                    if valor_anterior > 0:
                        factor_aplicado = valor_nuevo / valor_anterior
                    else:
                        factor_aplicado = Decimal(0)
                elif reval_type == 'porcentual':
                    factor_aplicado = Decimal(1) + (value / Decimal(100))
                    valor_nuevo = valor_anterior * factor_aplicado

                # 4. Crear registro de historial
                historial = RevalorizacionActivo.objects.create(
                    empresa=activo.empresa,
                    activo=activo,
                    valor_anterior=valor_anterior,
                    valor_nuevo=valor_nuevo,
                    factor_aplicado=factor_aplicado,
                    notas=notas,
                    realizado_por=request.user
                )

                # 5. Actualizar el valor del activo
                activo.valor_actual = valor_nuevo
                activo.save(update_fields=['valor_actual'])

            serializer = self.get_serializer(historial)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ActivoFijo.DoesNotExist:
            return Response({'detail': 'El activo no existe o no pertenece a tu empresa.'}, status=status.HTTP_404_NOT_FOUND)
        except Empleado.DoesNotExist:
            return Response({'detail': 'El perfil de empleado para este usuario no existe.'}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error en RevalorizacionActivoViewSet.ejecutar: {e}", exc_info=True)
            return Response({'detail': f'Error interno del servidor: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ItemCatalogoViewSet(BaseTenantViewSet):
    queryset = ItemCatalogo.objects.all()
    serializer_class = ItemCatalogoSerializer
    required_manage_permission = 'manage_item_catalogo' # Necesitarás crear este permiso
    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = ItemCatalogoFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['nombre', 'tipo_item']

class InventarioViewSet(BaseTenantViewSet):
    queryset = Inventario.objects.all().select_related('ubicacion', 'item_catalogo', 'responsable__usuario')
    serializer_class = InventarioSerializer
    required_manage_permission = 'manage_inventario' # Necesitarás crear este permiso
    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = InventarioFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['item_catalogo__nombre', 'ubicacion__nombre']

class MovimientoInventarioViewSet(BaseTenantViewSet):
    queryset = MovimientoInventario.objects.all().select_related('inventario__item_catalogo')
    serializer_class = MovimientoInventarioSerializer
    required_manage_permission = 'manage_inventario' # Permiso de inventario general
    # --- CONFIGURACIÓN DE FILTROS Y BÚSQUEDA ---
    filterset_class = MovimientoInventarioFilter
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ['descripcion']


class SuscripcionViewSet(BaseTenantViewSet):
    """
    ViewSet para que el Admin de la empresa vea su suscripción.
    Solo permitimos ver (GET), no editar. La edición se haría
    por un portal de pagos diferente (ej. Stripe).
    """
    queryset = Suscripcion.objects.all()
    serializer_class = SuscripcionSerializer
    required_manage_permission = 'view_suscripcion' # Permiso para ver
    http_method_names = ['get', 'head', 'options'] # Solo lectura

    def get_queryset(self):
        # Sobrescribimos para que solo devuelva LA suscripción de la empresa
        empleado = self.request.user.empleado
        return self.queryset.filter(empresa=empleado.empresa)

class NotificacionViewSet(BaseTenantViewSet):
    """
    ViewSet para la "campanita" de notificaciones en el Header.
    """
    queryset = Notificacion.objects.all()
    serializer_class = NotificacionSerializer
    required_manage_permission = 'view_dashboard' # Cualquiera que vea el dashboard puede verlas

    def get_queryset(self):
        """
        Modificado: Devuelve TODAS las notificaciones del USUARIO logueado,
        ordenadas por no leídas primero, y luego por fecha descendente.
        (Ya no filtra por empresa ni necesita caso especial SuperAdmin aquí).
        """
        # Filtrar directamente por el usuario autenticado
        user = self.request.user
        if not user.is_authenticated: # Seguridad extra
            return self.queryset.none()
        # print(f"DEBUG: NotificacionViewSet.get_queryset for user {user.id}")
        # Orden ya definido en Meta del modelo
        return self.queryset.filter(destinatario=user)
        
    @action(detail=True, methods=['post'], url_path='marcar-leido')
    def marcar_leido(self, request, pk=None):
        """Marcar como leída (Verifica que sea el destinatario)."""
        try:
            notificacion = self.get_object()
            # --- [CAMBIO] Verificar destinatario ---
            if notificacion.destinatario != request.user:
                return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)

            notificacion.leido = True
            notificacion.save()
            return Response({'status': 'Notificación marcada como leída'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='marcar-todo-leido')
    def marcar_todo_leido(self, request):
        """Marcar todas las del usuario como leídas."""
        try:
            # --- [CAMBIO] Filtrar por destinatario ---
            count, _ = Notificacion.objects.filter(destinatario=request.user, leido=False).update(leido=True)
            return Response({'status': f'{count} notificaciines marcadas como leídas'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)