from pathlib import Path
from datetime import timedelta
import os
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, '.env'))

# --- 1. CONFIGURACIÓN DE SEGURIDAD (CON VARIABLES DE ENTORNO) ---
# Estas variables las añadirás en el panel de Render
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG_VALUE', 'False') == 'True'

# Render te da esta variable automáticamente
ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# --- APLICACIONES INSTALADAS ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # --- LIBRERÍAS DE TERCEROS ---
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    # --- NUESTRA APP ---
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Correcto
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ActFijoSaaS.urls'
WSGI_APPLICATION = 'ActFijoSaaS.wsgi.application'
TEMPLATES = [ 
    # ... (tu configuración de templates está bien)
]


# --- 2. CONFIGURACIÓN DE BASE DE DATOS (LEYENDO VARIABLES DE ENTORNO) ---
# Aquí le decimos a Django que lea las 3 URLs de tus BD de Clever Cloud
# desde las variables de entorno que crearás en Render.

DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL', # Leerá la variable DATABASE_URL
        conn_max_age=600,
        ssl_require=True # Clever Cloud probablemente requiera SSL
    ),
    'log_saas': dj_database_url.config(
        env='LOG_SAAS_URL', # Leerá la variable LOG_SAAS_URL
        conn_max_age=600,
        ssl_require=True
    ),
    'analytics_saas': dj_database_url.config(
        env='ANALYTICS_SAAS_URL', # Leerá la variable ANALYTICS_SAAS_URL
        conn_max_age=600,
        ssl_require=True
    )
}

# ¡BUENA NOTICIA!
# Como estamos definiendo las 3 bases de datos, tu router SÍ funcionará.
DATABASE_ROUTERS = ['api.db_router.AnalyticsRouter']


# ... (Validadores de contraseña sin cambios)

# --- CONFIGURACIÓN DE INTERNACIONALIZACIÓN ---
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/La_Paz'
USE_I18N = True
USE_TZ = True

# --- ARCHIVOS ESTÁTICOS Y MEDIA (Igual que antes) ---
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') 
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
# RECUERDA: Los archivos subidos aquí se borrarán.
# Para una app real, necesitas Amazon S3 o similar.
MEDIA_ROOT = BASE_DIR / 'mediafiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CORS ---
# Añade la URL de tu frontend cuando la tengas
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    # "https://tu-frontend.onrender.com" 
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

SIMPLE_JWT = {
    # Duración del token de acceso (ej: 1 hora en desarrollo)
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60), 
    # Duración del token de refresco (ej: 1 día)
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1), 
    
    # --- Opciones estándar (generalmente no necesitas cambiarlas) ---
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY, # Usa la SECRET_KEY de Django
    "VERIFYING_KEY": "",
    "AUDIENCE": None,
    "ISSUER": None,
    "JSON_ENCODER": None,
    "JWK_URL": None,
    "LEEWAY": 0,

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",

    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",

    "JTI_CLAIM": "jti",

    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5), # No relevante si no usas sliding tokens
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1), # No relevante si no usas sliding tokens

    # --- IMPORTANTE: Apunta a tu serializer personalizado ---
    "TOKEN_OBTAIN_SERIALIZER": "api.serializers.MyTokenObtainPairSerializer", 
}
