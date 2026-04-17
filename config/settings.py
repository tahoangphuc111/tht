import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=None):
    value = os.getenv(name)
    if value is None:
        return default or []
    return [item.strip() for item in value.split(',') if item.strip()]


load_local_env(BASE_DIR / '.env')

SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-&=)qom7#3qdd(r^8_eivq+)wn2eos#rx9@=0z(u5w6e0e#*qz1',
)
DEBUG = env_bool('DJANGO_DEBUG', default=True)
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'])
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'martor',
    'wiki.apps.WikiConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DJANGO_DB_PATH', str(BASE_DIR / 'db.sqlite3')),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = os.getenv('DJANGO_LANGUAGE_CODE', 'vi')

TIME_ZONE = os.getenv('DJANGO_TIME_ZONE', 'Asia/Ho_Chi_Minh')

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
LOCAL_STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_DIRS = [LOCAL_STATIC_ROOT]

LOCAL_MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_ROOT = LOCAL_MEDIA_ROOT
MEDIA_URL = '/media/'

try:
    import channels  # noqa: F401
except ImportError:
    ASGI_APPLICATION = 'config.asgi.application'
else:
    if 'channels' not in INSTALLED_APPS:
        INSTALLED_APPS.append('channels')
    ASGI_APPLICATION = 'config.asgi.application'

STATICFILES_DIRS = [LOCAL_STATIC_ROOT]

MEDIA_URL = '/media/'
LOCAL_MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_ROOT = LOCAL_MEDIA_ROOT

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = 'wiki:article-list'

LOCAL_DEBUG = DEBUG

LOGOUT_REDIRECT_URL = 'wiki:login'


MARTOR_THEME = 'bootstrap'
MARTOR_ENABLE_CONFIGS = {
    'emoji': 'true',
    'imgur': 'true',
    'mention': 'true',
    'jquery': 'true',
    'living': 'true',
    'spellcheck': 'true',
    'hljs': 'true',
}
MARTOR_UPLOAD_URL = '/media/'
MARTOR_UPLOAD_PATH = str(MEDIA_ROOT)
MARTOR_UPLOAD_MAX_SIZE = 15 * 1024 * 1024  # 15MB cap for editor uploads
# Allowed content types for Martor upload endpoint:
MARTOR_ALLOWED_UPLOADS = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/png',
    'image/jpeg',
    'image/jpg',
]

try:
    from .local_settings import *
except ImportError:
    pass

