"""
Django settings for config project.
"""

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


def _resolve_python_binary(base_dir):
    """Return a reasonable default Python binary for code execution."""
    venv_python = base_dir / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return shutil.which("python") or shutil.which("py")


def _default_code_languages(base_dir):
    """Build default language configs that local_settings can override."""
    python_bin = _resolve_python_binary(base_dir)
    node_bin = shutil.which("node")
    java_bin = shutil.which("java")
    javac_bin = shutil.which("javac")
    gpp_bin = shutil.which("g++")
    gcc_bin = shutil.which("gcc")
    go_bin = shutil.which("go")
    rustc_bin = shutil.which("rustc")
    dotnet_bin = shutil.which("dotnet")

    return {
        "python": {
            "label": "Python 3",
            "monaco_language": "python",
            "source_name": "main.py",
            "compile": [],
            "run": [python_bin, "{source_path}"],
            "starter_code": (
                "def solve() -> None:\n"
                "    data = input().strip()\n"
                "    print(data)\n\n"
                "if __name__ == '__main__':\n"
                "    solve()\n"
            ),
            "enabled": bool(python_bin),
        },
        "cpp": {
            "label": "C++17",
            "monaco_language": "cpp",
            "source_name": "main.cpp",
            "compile": [
                gpp_bin,
                "-O2",
                "-std=c++17",
                "{source_path}",
                "-o",
                "{executable_path}",
            ],
            "run": ["{executable_path}"],
            "starter_code": (
                "#include <bits/stdc++.h>\n"
                "using namespace std;\n\n"
                "int main() {\n"
                "    ios::sync_with_stdio(false);\n"
                "    cin.tie(nullptr);\n\n"
                "    string s;\n"
                "    if (getline(cin, s)) cout << s << '\\n';\n"
                "    return 0;\n"
                "}\n"
            ),
            "enabled": bool(gpp_bin),
        },
        "c": {
            "label": "C11",
            "monaco_language": "c",
            "source_name": "main.c",
            "compile": [
                gcc_bin,
                "-O2",
                "-std=c11",
                "{source_path}",
                "-o",
                "{executable_path}",
            ],
            "run": ["{executable_path}"],
            "starter_code": (
                "#include <stdio.h>\n\n"
                "int main(void) {\n"
                "    char s[1005];\n"
                "    if (fgets(s, sizeof(s), stdin)) {\n"
                "        printf(\"%s\", s);\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            ),
            "enabled": bool(gcc_bin),
        },
        "java": {
            "label": "Java 17",
            "monaco_language": "java",
            "source_name": "Main.java",
            "compile": [javac_bin, "{source_path}"],
            "run": [java_bin, "-cp", "{workdir}", "Main"],
            "starter_code": (
                "import java.io.*;\n"
                "import java.util.*;\n\n"
                "public class Main {\n"
                "    public static void main(String[] args) throws Exception {\n"
                "        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));\n"
                "        String line = br.readLine();\n"
                "        if (line != null) System.out.println(line);\n"
                "    }\n"
                "}\n"
            ),
            "enabled": bool(java_bin and javac_bin),
        },
        "node": {
            "label": "Node.js",
            "monaco_language": "javascript",
            "source_name": "main.js",
            "compile": [],
            "run": [node_bin, "{source_path}"],
            "starter_code": (
                "const fs = require('fs');\n"
                "const input = fs.readFileSync(0, 'utf8').trim();\n"
                "console.log(input);\n"
            ),
            "enabled": bool(node_bin),
        },
        "go": {
            "label": "Go",
            "monaco_language": "go",
            "source_name": "main.go",
            "compile": [go_bin, "build", "-o", "{executable_path}", "{source_path}"],
            "run": ["{executable_path}"],
            "starter_code": (
                "package main\n\n"
                "import (\n"
                "    \"bufio\"\n"
                "    \"fmt\"\n"
                "    \"os\"\n"
                ")\n\n"
                "func main() {\n"
                "    in := bufio.NewScanner(os.Stdin)\n"
                "    if in.Scan() {\n"
                "        fmt.Println(in.Text())\n"
                "    }\n"
                "}\n"
            ),
            "enabled": bool(go_bin),
        },
        "rust": {
            "label": "Rust",
            "monaco_language": "rust",
            "source_name": "main.rs",
            "compile": [rustc_bin, "{source_path}", "-O", "-o", "{executable_path}"],
            "run": ["{executable_path}"],
            "starter_code": (
                "use std::io::{self, Read};\n\n"
                "fn main() {\n"
                "    let mut input = String::new();\n"
                "    io::stdin().read_to_string(&mut input).unwrap();\n"
                "    print!(\"{}\", input.trim());\n"
                "}\n"
            ),
            "enabled": bool(rustc_bin),
        },
        "csharp": {
            "label": "C#",
            "monaco_language": "csharp",
            "source_name": "Program.cs",
            "compile": [dotnet_bin, "build", "{project_path}", "-c", "Release", "-o", "{build_dir}"],
            "run": [dotnet_bin, "{dll_path}"],
            "starter_code": (
                "using System;\n\n"
                "class Program {\n"
                "    static void Main() {\n"
                "        var line = Console.ReadLine();\n"
                "        if (line != null) Console.WriteLine(line);\n"
                "    }\n"
                "}\n"
            ),
            "enabled": bool(dotnet_bin),
        },
    }


CODE_EXECUTION_ENABLED = True
CODE_EXECUTION_TMP_ROOT = Path(tempfile.gettempdir()) / "cpwiki_judge"
CODE_EXECUTION_MAX_SOURCE_BYTES = 128 * 1024
CODE_EXECUTION_MAX_OUTPUT_BYTES = 512 * 1024
CODE_EXECUTION_MAX_TESTCASES = 30
CODE_EXECUTION_MAX_CONCURRENT_JOBS = 2
CODE_EXECUTION_DEFAULT_TIME_LIMIT_MS = 2000
CODE_EXECUTION_DEFAULT_MEMORY_MB = 128
CODE_EXECUTION_ALLOWED_TESTCASE_EXTENSIONS = [".inp", ".out", ".txt", ".ans", ".in"]
CODE_EXECUTION_LANGUAGE_CONFIGS = _default_code_languages(BASE_DIR)

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
