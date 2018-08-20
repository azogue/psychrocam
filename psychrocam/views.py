# -*- coding: utf-8 -*-
import logging

from flask import request, redirect, url_for, jsonify

from psychrodata.redis_mng import get_var, set_var, has_var

from psychrochartmaker import (
    TASK_CLEAN_CACHE_DATA, TASK_CREATE_PSYCHROCHART, TASK_RELOAD_HA_CONFIG)
from psychrocam import (
    app, image_response, json_response, json_error, redis, celery,
    ROUTE_CHARTCONFIG, ROUTE_HA_CONFIG, ROUTE_HA_STATES,
    ROUTE_CLEAN_CACHE, ROUTE_SVGCHART, ROUTE_HA_EVOLUTION)


CHART_STYLE_KEYS = ['figure', 'limits', 'saturation', 'constant_rh',
                    'constant_v', 'constant_h', 'constant_wet_temp',
                    'constant_dry_temp', 'constant_humidity', 'chart_params',
                    'zones']
HA_CONFIG_KEYS = ['exterior', 'history', 'homeassistant',
                  'interior', 'location', 'sun']


# TODO Validate new config
def _update_dict(old_style, new_style, valid_keys):
    for key, value in new_style.items():
        if key in valid_keys and isinstance(old_style[key], dict):
            if isinstance(value, dict):
                old_style[key].update(value)
            else:
                old_style[key] = value
        elif key in valid_keys:
            old_style[key] = value


###############################################################################
# Routes
###############################################################################
@app.route(ROUTE_CHARTCONFIG, methods=['GET', 'POST'])
def psychrochart_config():
    if request.method == 'GET':
        if not has_var(redis, 'chart_style'):
            task = celery.send_task(TASK_CLEAN_CACHE_DATA)
            return json_error(
                404000, error_msg=f"No chart config available!, "
                                  f"resetting all (task: {task})")
        styles = get_var(redis, 'chart_style')
        styles['zones'] = get_var(redis, 'chart_zones')['zones']
        return json_response(styles)
    elif isinstance(request.json, dict) and request.json:
        new_data = request.json
        logging.warning(f"Set new chart style: {new_data}")

        styles = get_var(redis, 'chart_style')
        zones = get_var(redis, 'chart_zones')

        _update_dict(styles, new_data, CHART_STYLE_KEYS)
        _update_dict(zones, new_data, CHART_STYLE_KEYS)

        set_var(redis, 'chart_style', styles)
        set_var(redis, 'chart_zones', zones)
        set_var(redis, 'chart_config_changed', True)

        logging.debug('Make psychrochart now!')
        celery.send_task(TASK_CREATE_PSYCHROCHART)
        styles['zones'] = get_var(redis, 'chart_zones')['zones']
        return json_response({"new_config": new_data, "result": styles})
    return json_error(400, error_msg="Bad request! json: %s; args: %s",
                      msg_args=[request.json, request.args])


@app.route(ROUTE_HA_CONFIG, methods=['GET', 'POST'])
def homeassistant_config():
    if request.method == 'GET':
        if not has_var(redis, 'ha_yaml_config'):
            return json_error(
                404001, error_msg="No Home Assistant config available!, "
                                  "please POST one")

        return json_response(get_var(redis, 'ha_yaml_config'))
    elif isinstance(request.json, dict) and request.json:
        new_data = request.json
        logging.warning(f"Set new HA config: {new_data}")
        ha_config = get_var(redis, 'ha_yaml_config')
        _update_dict(ha_config, new_data, HA_CONFIG_KEYS)
        set_var(redis, 'ha_yaml_changed', True)
        set_var(redis, 'ha_yaml_config', ha_config)
        celery.send_task(TASK_RELOAD_HA_CONFIG)
        return json_response(ha_config)
    return json_error(400, error_msg="Bad request! json: %s; args: %s",
                      msg_args=[request.json, request.args])


@app.route(ROUTE_HA_STATES, methods=['GET'])
def homeassistant_states():
    if not has_var(redis, 'ha_states'):
        return json_error(
            404002, error_msg="No Home Assistant states available!")

    ha_states = get_var(redis, 'ha_states', unpickle_object=True)
    for s in ha_states:
        ha_states[s]['last_updated'] = ha_states[s]['last_updated'].isoformat()
        ha_states[s]['last_changed'] = ha_states[s]['last_changed'].isoformat()
    return json_response(ha_states)


@app.route(ROUTE_HA_EVOLUTION, methods=['GET'])
def get_homeassistant_sensors_evolution():
    ha_evolution = get_var(redis, 'ha_evolution')
    if ha_evolution:
        # Without response schema (direct use with HA REST sensor)
        return jsonify(ha_evolution)
    # Do something!
    return json_error(500002, error_msg="No history data available!")


@app.route(ROUTE_SVGCHART, methods=['GET'])
def get_svg_chart():
    svg = get_var(redis, 'svg_chart')
    if svg:
        return image_response(svg, image_type='svg')
    # Do something!
    return json_error(500001, error_msg="No SVG image available!")

    # TODO POST points/zones/etc


@app.route(ROUTE_CLEAN_CACHE, methods=['GET', 'POST'])
def clean_cache():
    # TODO remove GET method for cache cleaning
    if request.method == 'POST' or 'clean' in request.args:
        celery.send_task(TASK_CLEAN_CACHE_DATA)
        celery.send_task(TASK_CREATE_PSYCHROCHART, countdown=.5)
        # time_limit = None, soft_time_limit = None
        return json_response({"cache_cleaned": True})
    return json_error(405, "Can't clean the cache with args: %s", request.args)


@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('get_svg_chart'))
