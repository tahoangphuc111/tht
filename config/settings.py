"""
Django settings for config project.
"""

import json
import shutil
import tempfile
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-default-key-replace-in-production"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "martor",
    "taggit",
    "wiki",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wiki.context_processors.notifications_count",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation"
        ".UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation" ".MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation" ".CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation" ".NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "vi"

TIME_ZONE = "Asia/Ho_Chi_Minh"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
LOCAL_STATIC_ROOT = BASE_DIR / "static"
STATICFILES_DIRS = [LOCAL_STATIC_ROOT]

LOCAL_MEDIA_ROOT = BASE_DIR / "media"
MEDIA_ROOT = LOCAL_MEDIA_ROOT
MEDIA_URL = "/media/"

def _load_languages(base_dir):
    json_path = base_dir / "config" / "languages.json"
    if not json_path.exists():
        return {}

    with open(json_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    venv_py = base_dir / "venv" / "Scripts" / "python.exe"
    runtime_vars = {
        "source_path", "executable_path", "workdir",
        "project_path", "build_dir", "dll_path", "source_name",
    }
    resolved = {}

    for key, cfg in raw.items():
        candidates = cfg.get("binaries", [])
        bin_lookup = {}
        for name in candidates:
            if name in ("python", "python3", "py") and venv_py.exists():
                bin_lookup.setdefault("python", str(venv_py))
                bin_lookup.setdefault("python3", str(venv_py))
                bin_lookup.setdefault("py", str(venv_py))
            path = shutil.which(name)
            if path:
                bin_lookup.setdefault(name, path)

        def resolve(part):
            if not (part.startswith("{") and part.endswith("}")):
                return part
            bname = part[1:-1]
            if bname in runtime_vars:
                return part
            return bin_lookup.get(bname) or shutil.which(bname)

        compile_cmd = [resolve(p) for p in cfg.get("compile", [])]
        run_cmd = [resolve(p) for p in cfg.get("run", [])]
        has_missing = any(v is None for v in compile_cmd + run_cmd)

        resolved[key] = {
            "label": cfg.get("label", key),
            "monaco_language": cfg.get("monaco", "plaintext"),
            "source_name": cfg.get("source", f"main.{key}"),
            "compile": compile_cmd,
            "run": run_cmd,
            "starter_code": cfg.get("starter", ""),
            "enabled": not has_missing,
        }

    return resolved


CODE_EXECUTION_ENABLED = True
CODE_EXECUTION_TMP_ROOT = Path(tempfile.gettempdir()) / "cpwiki_judge"
CODE_EXECUTION_MAX_SOURCE_BYTES = 128 * 1024
CODE_EXECUTION_MAX_OUTPUT_BYTES = 512 * 1024
CODE_EXECUTION_MAX_TESTCASES = 30
CODE_EXECUTION_MAX_CONCURRENT_JOBS = 2
CODE_EXECUTION_DEFAULT_TIME_LIMIT_MS = 1000
CODE_EXECUTION_DEFAULT_MEMORY_MB = 128
CODE_EXECUTION_ALLOWED_TESTCASE_EXTENSIONS = [".inp", ".out", ".txt", ".ans", ".in"]
CODE_EXECUTION_LANGUAGE_CONFIGS = _load_languages(BASE_DIR)

try:
    # pylint: disable=unused-import
    import channels
except ImportError:
    ASGI_APPLICATION = "config.asgi.application"
else:
    if "channels" not in INSTALLED_APPS:
        INSTALLED_APPS.append("channels")
    ASGI_APPLICATION = "config.asgi.application"

# Authentication
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "wiki:article-list"
LOGOUT_REDIRECT_URL = "wiki:login"

# OAuth Placeholders (Set những giá trị này trong local_settings.py)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = None
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = None
SOCIAL_AUTH_GITHUB_KEY = None
SOCIAL_AUTH_GITHUB_SECRET = None

# Martor Configuration
MARTOR_THEME = "bootstrap"

MARTOR_ENABLE_CONFIGS = {
    "emoji": "true",
    "imgur": "true",
    "mention": "true",
    "jquery": "true",
    "living": "true",
    "spellcheck": "true",
    "hljs": "true",
}
MARTOR_UPLOAD_URL = "/media/"
MARTOR_UPLOAD_PATH = str(MEDIA_ROOT)
MARTOR_UPLOAD_MAX_SIZE = 15 * 1024 * 1024  # 15MB cap cho editor uploads
# Các loại file cho phép tải lên qua Martor:
MARTOR_ALLOWED_UPLOADS = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "image/jpg",
]

try:
    # pylint: disable=wildcard-import, unused-wildcard-import
    from .local_settings import *
except ImportError:
    pass
