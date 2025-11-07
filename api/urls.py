# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# --- [NUEVO] Imports para servir media files en DEBUG ---
from django.conf import settings
from django.conf.urls.static import static

from .views import (
    ReporteActivosPreview, ReporteActivosExport, CargoViewSet, DepartamentoViewSet,
    EmpleadoViewSet, ActivoFijoViewSet, PresupuestoViewSet, 
    RolesViewSet, LogViewSet, EstadoViewSet, UbicacionViewSet, ProveedorViewSet, PermisosViewSet,
    RegisterEmpresaView, MyTokenObtainPairView, UserPermissionsView, MantenimientoViewSet, OrdenesCompraViewSet, SuscripcionViewSet, NotificacionViewSet, ItemCatalogoViewSet, InventarioViewSet, MovimientoInventarioViewSet,
    MyThemePreferencesView, ReporteQueryView, ReporteQueryExportView, RevalorizacionActivoViewSet
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'cargos', CargoViewSet)
router.register(r'departamentos', DepartamentoViewSet)
router.register(r'empleados', EmpleadoViewSet)
router.register(r'activos-fijos', ActivoFijoViewSet)
router.register(r'presupuestos', PresupuestoViewSet)
router.register(r'roles', RolesViewSet)
router.register(r'logs', LogViewSet, basename='log')
router.register(r'estados', EstadoViewSet)
router.register(r'ubicaciones', UbicacionViewSet)
router.register(r'proveedores', ProveedorViewSet)
router.register(r'permisos', PermisosViewSet)
router.register(r'mantenimientos', MantenimientoViewSet, basename='mantenimiento')
router.register(r'ordenes-compra', OrdenesCompraViewSet, basename='orden_compra')
router.register(r'suscripcion', SuscripcionViewSet, basename='suscripcion')
router.register(r'notificaciones', NotificacionViewSet, basename='notificacion')
router.register(r'revalorizaciones', RevalorizacionActivoViewSet, basename='revalorizacion')
router.register(r'items-catalogo', ItemCatalogoViewSet, basename='item_catalogo')
router.register(r'inventarios', InventarioViewSet, basename='inventario')
router.register(r'movimientos-inventario', MovimientoInventarioViewSet, basename='movimiento_inventario')

urlpatterns = [
    ##path('reportes/activos-preview/', ReporteActivosPreview.as_view(), name='reporte_activos_preview'),
    ###path('reportes/activos-export/excel/', ReporteActivosExportExcel.as_view(), name='reporte_activos_export_excel'), # Nueva vista/URL
    ##path('reportes/activos-export/', ReporteActivosExport.as_view(), name='reporte_activos_export'),       
    path('reportes/query/', ReporteQueryView.as_view(), name='reporte_query_preview'),
    path('reportes/query/export/', ReporteQueryExportView.as_view(), name='reporte_query_export'),
    path('register/', RegisterEmpresaView.as_view(), name='register_empresa'),
    path('', include(router.urls)),
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('my-permissions/', UserPermissionsView.as_view(), name='my_permissions'),
    path('me/theme/', MyThemePreferencesView.as_view(), name='my_theme_preferences'),
]

# Sirve los archivos de MEDIA (fotos subidas) SOLO en modo DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)