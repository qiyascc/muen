"""
Django settings for mainscrpr project.
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-5dfs4sd5f4s5df45sdf54sd5f45sd4f5s'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    # Unfold admin theme
    'unfold',
    'unfold.contrib.filters',  # Optional for enhanced filters
    'unfold.contrib.forms',  # Optional for enhanced forms
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'lcwaikiki',
    'trendyol_app',  # Yeni Trendyol entegrasyon uygulaması
    'django_apscheduler',  # Django APScheduler for scheduling tasks
    # 'trendyol',  # Eski Trendyol uygulaması (devre dışı bırakıldı)
]

# Unfold settings
UNFOLD = {
    "SITE_TITLE": "LCWaikiki Admin",
    "SITE_HEADER": "LCWaikiki Management",
    "SITE_SYMBOL":
    "settings",  # Use an icon name from https://fonts.google.com/icons
    "SIDEBAR": {
        "show_search":
        True,
        "show_all_applications":
        True,
        "navigation": [
            {
                "title":
                "Dashboard",
                "items": [
                    {
                        "title": "LCWaikiki Dashboard",
                        "icon": "dashboard",
                        "link": "/dashboard/",
                    },
                    {
                        "title": "Trendyol Dashboard",
                        "icon": "analytics",
                        "link": "/trendyol/dashboard/",
                    },
                ],
            },
            {
                "title":
                "Configurations",
                "items": [
                    {
                        "title": "LCWaikiki Config",
                        "icon": "settings",
                        "link": "/admin/lcwaikiki/config/",
                    },
                    {
                        "title": "Trendyol API Config",
                        "icon": "api",
                        "link": "/admin/trendyol/trendyolapiconfig/",
                    },
                ],
            },
            {
                "title":
                "LCWaikiki Management",
                "items": [
                    {
                        "title": "Products",
                        "icon": "inventory_2",
                        "link": "/admin/lcwaikiki/product/",
                    },
                    {
                        "title": "Cities",
                        "icon": "location_city",
                        "link": "/admin/lcwaikiki/city/",
                    },
                    {
                        "title": "Stores",
                        "icon": "store",
                        "link": "/admin/lcwaikiki/store/",
                    },
                ],
            },
            {
                "title":
                "Trendyol Management",
                "items": [
                    {
                        "title": "Products",
                        "icon": "inventory_2",
                        "link": "/admin/trendyol/trendyolproduct/",
                    },
                    {
                        "title": "Brands",
                        "icon": "branding_watermark",
                        "link": "/admin/trendyol/trendyolbrand/",
                    },
                    {
                        "title": "Categories",
                        "icon": "category",
                        "link": "/admin/trendyol/trendyolcategory/",
                    },
                    {
                        "title": "Sync Status",
                        "icon": "sync",
                        "link": "/trendyol/sync-status/",
                    },
                ],
            },
            {
                "title":
                "URL Management",
                "items": [
                    {
                        "title": "Available URLs",
                        "icon": "check_circle",
                        "link": "/admin/lcwaikiki/productavailableurl/",
                    },
                    {
                        "title": "Deleted URLs",
                        "icon": "delete",
                        "link": "/admin/lcwaikiki/productdeletedurl/",
                    },
                    {
                        "title": "New URLs",
                        "icon": "add_circle",
                        "link": "/admin/lcwaikiki/productnewurl/",
                    },
                ],
            },
            {
                "title":
                "Scraper",
                "items": [
                    {
                        "title": "Scheduled Jobs",
                        "icon": "schedule",
                        "link": "/admin/django_apscheduler/djangojob/",
                    },
                    {
                        "title": "Job Executions",
                        "icon": "history",
                        "link":
                        "/admin/django_apscheduler/djangojobexecution/",
                    },
                ],
            },
        ],
    },
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mainscrpr.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mainscrpr.wsgi.application'

# Database
import os

# Use PostgreSQL instead of SQLite to avoid database locking issues
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('PGDATABASE', 'postgres'),
        'USER': os.environ.get('PGUSER', 'postgres'),
        'PASSWORD': os.environ.get('PGPASSWORD', ''),
        'HOST': os.environ.get('PGHOST', 'localhost'),
        'PORT': os.environ.get('PGPORT', '5432'),
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
        'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'tr-TR'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CSRF Trusted Origins - allowing Replit domains
CSRF_TRUSTED_ORIGINS = [
    'https://*.replit.dev',
    'https://*.replit.app',
    'https://*.repl.co',
]

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Django APScheduler settings
SCHEDULER_CONFIG = {
    "apscheduler.jobstores.default": {
        "class": "django_apscheduler.jobstores:DjangoJobStore"
    },
    "apscheduler.executors.processpool": {
        "type": "threadpool",
        "max_workers": 5
    }
}
SCHEDULER_AUTOSTART = True
SCHEDULER_TIMEZONE = "UTC"

# API keys and tokens
import os
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TRENDYOL_SUPPLIER_ID = os.environ.get("TRENDYOL_SUPPLIER_ID", "199999")
TRENDYOL_API_KEY = os.environ.get("TRENDYOL_API_KEY", "your-api-key")
TRENDYOL_API_SECRET = os.environ.get("TRENDYOL_API_SECRET", "your-api-secret")
SOPYO_API_TOKEN = os.environ.get("SOPYO_API_TOKEN", "1ba49fbfc39f233229242b89e0a3baeecFEDL")
