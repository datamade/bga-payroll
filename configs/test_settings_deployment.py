# This should be False in production!
DEBUG = True

SECRET_KEY = 'a very secret string'

INTERNAL_IPS = ['127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'bga_payroll',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

AWS_STORAGE_BUCKET_NAME = '<bucket_name>'
AWS_ACCESS_KEY_ID = '<key>'
AWS_SECRET_ACCESS_KEY = '<secret>'

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_FMT = 'redis://{host}:{port}/{db}'
REDIS_URL = REDIS_FMT.format(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

CELERY_BROKER_URL = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

CENSUS_API_KEY = '<A KEY>'

SOLR_URL = 'http://127.0.0.1:8983/solr/bga'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    },
    'api': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    },
    'vary_on_setting': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    },
}

CACHE_SECRET_KEY = 'a key'

# Email configuration for password reset loop
EMAIL_HOST = 'smtp.example.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'testing@example.com'
EMAIL_HOST_PASSWORD = 'secret password'
DEFAULT_FROM_EMAIL = ''  # e.g., 'testing@example.com'

# Configure Mailchimp
# https://mailchimp.com/developer/marketing/guides/quick-start/#make-your-first-api-call
MAILCHIMP_API_KEY = '<secret key>'
MAILCHIMP_SERVER = '<server code>'
MAILCHIMP_LIST_ID = '<id of list to search within>'
MAILCHIMP_INTEREST_ID = '<id of an interest/group>'
MAILCHIMP_TAG = '<name of the tag to attach to users>'  # e.g. 'Database Sign-up'

# Name and domain for cookie set for authorized users
MAILCHIMP_AUTH_COOKIE_NAME = ''  # e.g., mailchimp-auth
MAILCHIMP_AUTH_COOKIE_DOMAIN = ''  # e.g., datamade.us

# Location to which user will be redirected on authorization
MAILCHIMP_AUTH_REDIRECT_LOCATION = '/'
