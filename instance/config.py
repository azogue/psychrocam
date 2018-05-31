# -*- coding: utf-8 -*-
import os


###############################################################################
# Env vars
###############################################################################
docker_run = os.getenv('RUNNING_IN_DOCKER') or False
log_level = os.getenv('LOGGING_LEVEL') or 'INFO'

redis_h = 'redis' if docker_run else 'localhost'
redis_p = 6379
redis_dbidx0 = 0
redis_dbidx1 = 1
redis_pwd = os.getenv('REDIS_PWD')
redis_url = os.getenv('REDIS_URL') \
            or f'redis://:{redis_pwd}@{redis_h}:{redis_p}/{redis_dbidx0}'

secret_key = os.getenv('SECRET_KEY') or 'secretkeyforflask'
security_password_salt = os.getenv('SECURITY_PASSWORD_SALT') \
                         or 'longersecretkeyforflask'


###############################################################################
# JSON API config - Flask, Redis
###############################################################################
class Config(object):
    """Parent configuration class."""
    DEBUG = False
    TESTING = False

    # Forms protection
    CSRF_ENABLED = True
    SECRET = secret_key
    SECRET_KEY = secret_key
    # SECURITY_PASSWORD_SALT = security_password_salt
    # app.config['WTF_CSRF_ENABLED'] = True
    JSONIFY_PRETTYPRINT_REGULAR = True
    LOG_LEVEL = log_level

    # Redis config
    REDIS_HOST = 'redis' if docker_run else 'localhost'
    REDIS_PORT = redis_p
    REDIS_DB = redis_dbidx0
    REDIS_PASSWORD = redis_pwd

    # Celery config
    CELERY_BROKER_URL = redis_url
    CELERY_RESULT_BACKEND = redis_url


class DevelopmentConfig(Config):
    """Configurations for Development."""
    DEBUG = True
    # API_PREFIX = '/api_v2'
    API_PREFIX = ''

    REDIS_DB = redis_dbidx1


class TestingConfig(Config):
    """Configurations for Testing, with a separate test database."""
    TESTING = True
    DEBUG = True
    API_PREFIX = '/api_v3'

    REDIS_DB = redis_dbidx1


class ProductionConfig(Config):
    """Configurations for Production."""
    DEBUG = False
    TESTING = False
    API_PREFIX = '/api_v0'


app_config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
