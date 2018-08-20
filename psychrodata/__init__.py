# -*- coding: utf-8 -*-
from datetime import timedelta
import os


__version__ = '0.1'


log_level = os.getenv('LOGGING_LEVEL') or 'INFO'
prefix_web = os.getenv('API_PREFIX') or ''
redis_pwd = os.getenv('REDIS_PWD') or ''
redis_host = 'redis'
redis_port = 6379
redis_db = 0
redis_url = os.getenv('REDIS_URL') or f'redis://:{redis_pwd}' \
                                      f'@{redis_host}:{redis_port}/{redis_db}'


class Config(object):
    """Parent configuration class."""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = log_level
    PREFIX_WEB = prefix_web

    # Forms protection
    # CSRF_ENABLED = True
    # SECRET = secrets['secret_key']
    # SECRET_KEY = secrets['secret_key']
    # SECRET_BASIC_AUTH_KEY = secrets['secret_basic_auth_key']
    # SECURITY_PASSWORD_SALT = secrets['security_password_salt']

    # Redis
    REDIS_HOST = redis_host
    REDIS_PORT = redis_port
    REDIS_DB = redis_db
    REDIS_PASSWORD = redis_pwd

    # Celery
    CELERY_BROKER_URL = redis_url
    CELERY_RESULT_BACKEND = redis_url
    CELERY_TASK_IGNORE_RESULT = True
    CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True
    CELERY_TASK_RESULT_EXPIRES = timedelta(seconds=300)
