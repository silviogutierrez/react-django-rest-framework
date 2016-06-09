SECRET_KEY = 'dummy'

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'react_drf',
    'tests',
]

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

ROOT_URLCONF = 'tests.urls'

DEBUG = True

TEMPLATE_DEBUG = True
