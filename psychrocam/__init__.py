# -*- coding: utf-8 -*-
import logging
from math import floor
import os
import sys
from time import time

# noinspection PyUnresolvedReferences
from flask import Flask, jsonify, make_response, g
from flask_redis import Redis
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.exceptions import default_exceptions, HTTPException
from werkzeug.routing import Rule

from psychrodata import Config
# noinspection PyUnresolvedReferences
from psychrodata.redis_mng import get_celery, get_var, set_var

__version__ = '0.1'


###############################################################################
# LOG SETTINGS
###############################################################################
logging_conf = {
    "level": Config.LOG_LEVEL,
    "datefmt": '%d/%m/%Y %H:%M:%S',
    "format": '%(levelname)s [%(filename)s_%(funcName)s] '
              '- %(asctime)s: %(message)s'}
logging.basicConfig(**logging_conf)

###############################################################################
# Flask app
###############################################################################
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__,
            static_url_path=Config.PREFIX_WEB + '/static',
            static_folder=os.path.join(basedir, 'static'))
app.config.from_object(Config)
if Config.PREFIX_WEB:
    app.url_rule_class = lambda path, **options: Rule(
        Config.PREFIX_WEB + path, **options)
app.logger.addHandler(logging.StreamHandler())

###############################################################################
# Redis in-memory-DB
###############################################################################
redis = Redis(app)


###############################################################################
# Celery
###############################################################################
def create_celery(flask_app):
    celery_obj = get_celery(flask_app.import_name)
    # celery_obj.conf.update(flask_app.config)

    # noinspection PyPep8Naming
    TaskBase = celery_obj.Task

    class ContextTask(TaskBase):  # pragma: no cover
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery_obj.Task = ContextTask
    return celery_obj


celery = create_celery(app)

###############################################################################
# ROUTES
###############################################################################
ROUTE_HA_CONFIG = '/ha_config'
ROUTE_HA_STATES = '/ha_states'
ROUTE_HA_EVOLUTION = '/ha_evolution'
ROUTE_CHARTCONFIG = '/chartconfig'
ROUTE_SVGCHART = '/svgchart'
ROUTE_CLEAN_CACHE = '/clean'


###############################################################################
# JSON/IMAGE RESPONSE SCHEMA
###############################################################################
@app.before_request
def _set_tic_for_calc_request_took_time():
    g.tic_request = time()


ATTR_RESULT_OK = 'result_ok'
ATTR_RESULTS = 'result'
ATTR_TOKEN = 'token'
ATTR_ERROR = "error"
ATTR_ERROR_CODE = "code"
ATTR_ERROR_MSG = "msg"
ATTR_TOOK = 'took'
ATTR_TEMPERATURE = 'temperature'
ATTR_HUMIDITY = 'humidity'

SVG_MIMETYPE = 'image/svg+xml'
JSON_MIMETYPE = 'application/json'
MIMETYPES = {
    'svg': SVG_MIMETYPE,
    'json': JSON_MIMETYPE}


def image_response(bytes_image, image_type='svg'):
    # try:
    mimetype = MIMETYPES[image_type]
    # except KeyError:
    #     mimetype = JSON_MIMETYPE

    tic = g.get('tic_request')
    took = time() - tic
    logging.info(f"IMG RESPONSE [{image_type}] took {took:.4f}s")
    response = make_response(bytes_image, 200)
    response.mimetype = mimetype
    return response


def json_response(data_response, result_ok=None, status_code=200):
    error = result = None
    if result_ok is None:
        result_ok = status_code == 200

    if result_ok:
        result = data_response
    else:
        error = data_response

    tic = g.get('tic_request')
    took = time() - tic
    params = {ATTR_RESULT_OK: result_ok,
              ATTR_RESULTS: result,
              ATTR_TOOK: took,
              ATTR_ERROR: error}

    data = jsonify(**params)
    response = make_response(data, status_code)
    response.mimetype = JSON_MIMETYPE
    logging.info(f"JSON RESPONSE [{status_code}] took {took:.4f}s")
    return response


def json_error(error_code, error_msg='', msg_args=None):
    # try:
    #     msg = ERROR_CODES[error_code]
    # except KeyError:
    msg = error_msg
    if msg_args is not None:
        msg = msg.format(*msg_args)
    data_response = {ATTR_ERROR_CODE: error_code,
                     ATTR_ERROR_MSG: msg}

    if error_code != 404:
        logging.warning('API ERROR {}: {} [{}, from {}]'.format(
            error_code, msg, request.url, request.remote_addr))

    if error_code > 1000:
        status_code = int(floor(error_code / 1000))
    else:
        status_code = error_code
    return json_response(data_response, result_ok=False,
                         status_code=status_code)


###############################################################################
# Register exceptions as JSON responses
###############################################################################
def handle_error(exc):
    """Generic error handler to return always JSON."""
    return json_error(
        error_code=(exc.code if isinstance(exc, HTTPException) else 500),
        error_msg=f"URL: {request.url}, "
                  f"IP: {request.remote_addr}, ERROR: {str(exc)}")


for ex in default_exceptions:
    app.register_error_handler(ex, handle_error)


###############################################################################
# Celery workers VS flask server
###############################################################################
logging.info(f"***IMPORTED {__name__}[v:{__version__}]*** "
             f"with ARGS: {sys.argv}")

if sys.argv[0].endswith('celery'):
    if 'beat' not in sys.argv:
        logging.critical(f"CELERY BEAT NOT detected??: {sys.argv}")
        sys.exit(-1)

    # Celery beat, here we define the task scheduler
    logging.warning(f"CELERY BEAT detected: {sys.argv}")

    # noinspection PyUnusedLocal
    @celery.on_after_configure.connect
    def init_chart_config(sender, **kwargs):
        # from psychrochartmaker import TASK_PERIODIC_GET_HA_STATES
        from psychrochartmaker import TASK_CLEAN_CACHE_DATA
        from psychrochartmaker.tasks import periodic_get_ha_states

        logging.warning(f"On INIT_CHART_CONFIG")
        task = celery.send_task(TASK_CLEAN_CACHE_DATA)
        task.get()

        # Program HA polling schedule
        ha_history = get_var(redis, 'ha_history')
        scheduler = sender.add_periodic_task(
            ha_history['scan_interval'],
            periodic_get_ha_states.s(),
            name='HA sensor update')
        logging.info(f'DEBUG scheduler: {scheduler}')
        set_var(redis, 'scheduler', scheduler)

        # Make first psychrochart
        celery.send_task('create_psychrochart')
        return True
else:
    # noinspection PyUnresolvedReferences,PyPep8
    from psychrocam.views import *

    ###########################################################################
    # wsgi app
    ###########################################################################
    app.wsgi_app = ProxyFix(app.wsgi_app)

# mark init in log
logging.warning(f"***INIT*** with: Log level: {Config.LOG_LEVEL}, "
                f"Debug: {app.config['DEBUG']}, "
                f"Testing: {app.config['TESTING']}, "
                f"API prefix: {Config.PREFIX_WEB}, "
                f"Redis URL: {app.config['CELERY_BROKER_URL']}\n"
                f"ARGS: {sys.argv}")
