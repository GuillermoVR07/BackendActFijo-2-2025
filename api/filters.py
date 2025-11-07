import django_filters
from .models import ActivoFijo, Proveedor, Empleado, Mantenimiento, OrdenesCompra, ItemCatalogo, Inventario, MovimientoInventario, Presupuesto, Ubicacion, Estado

class ActivoFijoFilter(django_filters.FilterSet):
    # Filtro para buscar texto dentro del nombre (insensible a mayúsculas)
    nombre = django_filters.CharFilter(field_name='nombre', lookup_expr='icontains')

    # Filtros para rangos de fechas de adquisición
    fecha_min = django_filters.DateFilter(field_name='fecha_adquisicion', lookup_expr='gte')
    fecha_max = django_filters.DateFilter(field_name='fecha_adquisicion', lookup_expr='lte')

    # Filtros para rangos de valor
    valor_min = django_filters.NumberFilter(field_name='valor_actual', lookup_expr='gte')
    valor_max = django_filters.NumberFilter(field_name='valor_actual', lookup_expr='lte')

    class Meta:
        model = ActivoFijo
        # Aquí definimos los campos por los que se puede filtrar con coincidencia exacta.
        # Añadimos los campos de los filtros personalizados para que DRF los reconozca.
        fields = [
            'nombre', 'fecha_min', 'fecha_max', 'valor_min', 'valor_max',
            'departamento', 'estado', 'proveedor'
        ]

class ProveedorFilter(django_filters.FilterSet):
    nombre = django_filters.CharFilter(field_name='nombre', lookup_expr='icontains')
    nit = django_filters.CharFilter(field_name='nit', lookup_expr='icontains')
    pais = django_filters.CharFilter(field_name='pais', lookup_expr='icontains')

    class Meta:
        model = Proveedor
        fields = ['nombre', 'nit', 'pais', 'estado']

class EmpleadoFilter(django_filters.FilterSet):
    nombre = django_filters.CharFilter(field_name='usuario__first_name', lookup_expr='icontains')

    class Meta:
        model = Empleado
        fields = ['nombre', 'departamento', 'cargo', 'roles']

class MantenimientoFilter(django_filters.FilterSet):
    fecha_inicio_min = django_filters.DateFilter(field_name='fecha_inicio', lookup_expr='gte')
    fecha_inicio_max = django_filters.DateFilter(field_name='fecha_inicio', lookup_expr='lte')

    class Meta:
        model = Mantenimiento
        fields = ['activo', 'empleado_asignado', 'tipo', 'estado', 'fecha_inicio_min', 'fecha_inicio_max']

class OrdenesCompraFilter(django_filters.FilterSet):
    fecha_inicio_min = django_filters.DateFilter(field_name='fecha_inicio', lookup_expr='gte')
    fecha_inicio_max = django_filters.DateFilter(field_name='fecha_inicio', lookup_expr='lte')

    class Meta:
        model = OrdenesCompra
        fields = ['proveedor', 'solicitante', 'estado', 'fecha_inicio_min', 'fecha_inicio_max']

class ItemCatalogoFilter(django_filters.FilterSet):
    nombre = django_filters.CharFilter(field_name='nombre', lookup_expr='icontains')
    tipo_item = django_filters.CharFilter(field_name='tipo_item', lookup_expr='icontains')

    class Meta:
        model = ItemCatalogo
        fields = ['nombre', 'tipo_item']

class InventarioFilter(django_filters.FilterSet):
    cantidad_min = django_filters.NumberFilter(field_name='cantidad', lookup_expr='gte')
    cantidad_max = django_filters.NumberFilter(field_name='cantidad', lookup_expr='lte')

    class Meta:
        model = Inventario
        fields = ['ubicacion', 'item_catalogo', 'responsable', 'cantidad_min', 'cantidad_max']

class MovimientoInventarioFilter(django_filters.FilterSet):
    fecha_min = django_filters.DateFilter(field_name='fecha', lookup_expr='gte')
    fecha_max = django_filters.DateFilter(field_name='fecha', lookup_expr='lte')

    class Meta:
        model = MovimientoInventario
        fields = ['inventario', 'tipo_movimiento', 'fecha_min', 'fecha_max']

class PresupuestoFilter(django_filters.FilterSet):
    fecha_min = django_filters.DateFilter(field_name='fecha', lookup_expr='gte')
    fecha_max = django_filters.DateFilter(field_name='fecha', lookup_expr='lte')

    class Meta:
        model = Presupuesto
        fields = ['departamento', 'fecha_min', 'fecha_max']

class UbicacionFilter(django_filters.FilterSet):
    nombre = django_filters.CharFilter(field_name='nombre', lookup_expr='icontains')
    class Meta:
        model = Ubicacion
        fields = ['nombre']

class EstadoFilter(django_filters.FilterSet):
    nombre = django_filters.CharFilter(field_name='nombre', lookup_expr='icontains')
    class Meta:
        model = Estado
        fields = ['nombre']
