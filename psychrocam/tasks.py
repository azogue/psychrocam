# -*- coding: utf-8 -*-
import logging
import sys

from psychrocam import celery
from psychrocam.common import (
    load_chart_styles, load_chart_zones, load_homeassistant_config,
    save_homeassistant_config, save_chart_style, save_chart_zones)
from psychrocam.ha_remote_polling import (
    get_states, make_points_from_states, get_ha_api, parse_config_ha)
from psychrocam.make_charts import make_psychrochart
from psychrocam.redis_mng import (
    get_var, set_var, has_var, remove_var, clean_all_vars)


###############################################################################
# Celery Tasks
###############################################################################
def _log_task_init(task_name):
    logging.debug(f"In task {task_name}() [from CMD: {' '.join(sys.argv)}]")


def _load_chart_config():
    if not has_var('chart_style'):
        set_var('chart_style', load_chart_styles())
    if not has_var('chart_zones'):
        set_var('chart_zones', load_chart_zones())
    logging.info('CHART CONFIG LOADED')


def _load_homeassistant_config():
    yaml_config = get_var('ha_yaml_config')
    if yaml_config is None:
        yaml_config = load_homeassistant_config()
    parse_config_ha(yaml_config)


def _clean_all():
    clean_all_vars()
    logging.warning('CACHE DATA CLEANED')


@celery.task()
def clean_cache_data():
    _log_task_init("clean_cache_data")
    _clean_all()
    _load_chart_config()
    _load_homeassistant_config()
    return True


# noinspection PyUnusedLocal
@celery.on_after_configure.connect
def init_chart_config(sender, **kwargs):
    if 'beat' not in sys.argv:  # it's a celery worker, do nothing
        _log_task_init("init_chart_config[worker]")
        return False

    _log_task_init("init_chart_config")
    # if clean_cache:
    _clean_all()
    _load_chart_config()
    _load_homeassistant_config()

    # Program HA polling schedule
    ha_history = get_var('ha_history')
    scheduler = sender.add_periodic_task(
        ha_history['scan_interval'],
        periodic_get_ha_states.s(),
        name='HA sensor update')
    logging.info(f'DEBUG scheduler: {scheduler}')
    set_var('scheduler', scheduler)

    # Make first psychrochart
    make_psychrochart()

    return True


@celery.task()
def create_psychrochart():
    make_psychrochart()


@celery.task()
def reload_ha_config():
    remove_var('ha_config')
    remove_var('ha_api')
    remove_var('ha_sensors')
    remove_var('ha_states')
    remove_var('last_points')
    remove_var('points_unknown')
    remove_var('deque_points')
    remove_var('arrows')

    # TODO Reset/restart periodic task
    # if 'history' in new_data:  # Reset periodic task
    #     scheduler = get_var('scheduler')
    #     celery.tasks()
    #     celery.add_periodic_task()

    periodic_get_ha_states()


@celery.task()
def periodic_get_ha_states():
    """Background task to update the HA sensors states."""
    _log_task_init("periodic_get_ha_states")

    _load_homeassistant_config()
    if not has_var('ha_api'):
        get_ha_api()
    states = get_states()
    if not states:
        logging.error(f"Can't load HA states!")
        return {}

    make_points_from_states(states)
    ok = make_psychrochart()

    if ok and get_var('ha_yaml_changed'):
        # HA Configuration changed, and the result is OK, saving it now
        logging.warning('Saving HA config to disk '
                        '(after producing successfully one chart)')
        save_homeassistant_config(get_var('ha_yaml_config'))
        remove_var('ha_yaml_changed')
        remove_var('ha_yaml_config')
        _load_homeassistant_config()

    if ok and get_var('chart_config_changed'):
        # HA Configuration changed, and the result is OK, saving it now
        logging.warning('Saving PsychroChart config to disk '
                        '(after producing successfully one chart)')
        save_chart_style(get_var('chart_style'))
        save_chart_zones(get_var('chart_zones'))
        remove_var('chart_config_changed')
        remove_var('chart_style')
        remove_var('chart_zones')
        _load_chart_config()

    return ok
