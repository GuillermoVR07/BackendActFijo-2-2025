# ActFijoSaaS/urls.py
from django.contrib import admin
from django.urls import path, include

# --- [ NUEVO: Imports necesarios ] ---
from django.conf import settings
from django.conf.urls.static import static
# --- [ FIN NUEVO ] ---

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')), # Incluye las URLs de tu app 'api'
]

# --- [ NUEVO: Añadir esta línea al FINAL ] ---
# Sirve los archivos de MEDIA (fotos subidas) SOLO en modo DEBUG (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# --- [ FIN NUEVO ] ---