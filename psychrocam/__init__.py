# -*- coding: utf-8 -*-
import logging
from math import floor
import os
import sys
from time import time

from celery import Celery
from flask import Flask, jsonify, make_response, g
from flask_redis import Redis
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.exceptions import default_exceptions, HTTPException
from werkzeug.routing import Rule

from instance.config import app_config


__version__ = '0.1'

###############################################################################
# local import
###############################################################################
config_name = os.getenv('APP_SETTINGS') or "development"
docker_run = os.getenv('RUNNING_IN_DOCKER') or False
config_object = app_config[config_name]
prefix_web = config_object.API_PREFIX
log_level = config_object.LOG_LEVEL

###############################################################################
# LOG SETTINGS
###############################################################################
basedir = os.path.abspath(os.path.dirname(__file__))
logging_conf = {
    "level": log_level,
    "datefmt": '%d/%m/%Y %H:%M:%S',
    "format": '%(levelname)s [%(filename)s_%(funcName)s] '
              '- %(asctime)s: %(message)s'}
# if not docker_run:
#     logging_conf["filename"] = os.path.join(basedir, 'psychrocam_api.log')
logging.basicConfig(**logging_conf)

###############################################################################
# Flask app
###############################################################################
STATIC_PATH = os.path.join(basedir, 'static')

app = Flask(__name__,
            static_url_path=prefix_web + '/static',
            static_folder=STATIC_PATH)
# app = FlaskAPI(__name__, instance_relative_config=True)
app.config.from_object(config_object)
app.url_rule_class = lambda path, **options: Rule(prefix_web + path, **options)
app.logger.addHandler(logging.StreamHandler())


###############################################################################
# Redis in-memory-DB
###############################################################################
redis = Redis(app)

###############################################################################
# Celery
###############################################################################
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)
# celery.select_queues()

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
    # noinspection PyUnresolvedReferences,PyPep8
    from psychrocam.tasks import *
else:
    # noinspection PyUnresolvedReferences,PyPep8
    from psychrocam.views import *

    ###########################################################################
    # wsgi app
    ###########################################################################
    app.wsgi_app = ProxyFix(app.wsgi_app)

    # mark init in log
    logging.debug(f"***INIT*** in {config_name.upper()} mode, with: "
                  f"Log level: {log_level}, "
                  f"Docker: {docker_run}, "
                  f"Debug: {app.config['DEBUG']}, "
                  f"Testing: {app.config['TESTING']}, "
                  f"API prefix: {prefix_web}, "
                  f"prop. exceptions: {app.config['PROPAGATE_EXCEPTIONS']}"
                  f"Redis URL: {app.config['CELERY_BROKER_URL']}\n"
                  f"ARGS: {sys.argv}")
