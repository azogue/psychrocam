# -*- coding: utf-8 -*-
import logging
import sys

from celery import shared_task

from psychrodata.common import (
    load_chart_styles, load_chart_zones, load_homeassistant_config,
    save_homeassistant_config, save_chart_style, save_chart_zones)
from psychrodata.redis_mng import (
    get_redis, get_celery,
    get_var, set_var, has_var, remove_var, clean_all_vars)

from psychrochartmaker import (
    TASK_CLEAN_CACHE_DATA, TASK_CREATE_PSYCHROCHART, TASK_RELOAD_HA_CONFIG,
    TASK_PERIODIC_GET_HA_STATES)
from psychrochartmaker.ha_remote_polling import (
    get_ha_states, make_points_from_states, get_ha_api, parse_config_ha)
from psychrochartmaker.make_charts import make_psychrochart


redis = get_redis()
celery = get_celery('chartworker')


###############################################################################
# Celery Tasks
###############################################################################
def _log_task_init(task_name):
    logging.debug(f"In task {task_name}() [from CMD: {' '.join(sys.argv)}]")


def _load_chart_config():
    if not has_var(redis, 'chart_style'):
        set_var(redis, 'chart_style', load_chart_styles())
    if not has_var(redis, 'chart_zones'):
        set_var(redis, 'chart_zones', load_chart_zones())
    logging.info('CHART CONFIG LOADED')


def _load_homeassistant_config():
    yaml_config = get_var(redis, 'ha_yaml_config')
    if yaml_config is None:
        yaml_config = load_homeassistant_config()
    parse_config_ha(redis, yaml_config)


def _clean_all():
    clean_all_vars(redis)
    logging.warning('CACHE DATA CLEANED')


@shared_task(name=TASK_CLEAN_CACHE_DATA)
def clean_cache_data():
    _log_task_init("clean_cache_data")
    _clean_all()
    _load_chart_config()
    _load_homeassistant_config()
    return True


@shared_task(name=TASK_CREATE_PSYCHROCHART)
def create_psychrochart():
    make_psychrochart(redis)
    return True


@shared_task(name=TASK_RELOAD_HA_CONFIG)
def reload_ha_config():
    remove_var(redis, 'ha_config')
    remove_var(redis, 'ha_api')
    remove_var(redis, 'ha_sensors')
    remove_var(redis, 'ha_states')
    remove_var(redis, 'last_points')
    remove_var(redis, 'points_unknown')
    remove_var(redis, 'deque_points')
    remove_var(redis, 'arrows')

    # TODO Reset/restart periodic task
    # if 'history' in new_data:  # Reset periodic task
    #     scheduler = get_var(redis, 'scheduler')
    #     celery.tasks()
    #     celery.add_periodic_task()

    periodic_get_ha_states()
    return True


@shared_task(name=TASK_PERIODIC_GET_HA_STATES)
def periodic_get_ha_states():
    """Background task to update the HA sensors states."""
    making_chart_now = get_var(redis, 'making_chart_now', default=0)
    if making_chart_now:
        logging.warning('last periodic_get_ha_states is not finished. '
                        'Aborting this try...')
        return

    set_var(redis, 'making_chart_now', 1)
    _log_task_init("periodic_get_ha_states")

    _load_homeassistant_config()
    if not has_var(redis, 'ha_api'):
        get_ha_api(redis)
    logging.debug('loading states...')
    states = get_ha_states(redis)
    if not states:
        logging.error(f"Can't load HA states!")
        set_var(redis, 'making_chart_now', False)
        return

    logging.debug('making points...')
    make_points_from_states(redis, states)
    logging.debug('making chart...')
    ok = make_psychrochart(redis)
    logging.debug('chart DONE')
    set_var(redis, 'making_chart_now', 0)

    if ok and get_var(redis, 'ha_yaml_changed'):
        # HA Configuration changed, and the result is OK, saving it now
        logging.warning('Saving HA config to disk '
                        '(after producing successfully one chart)')
        save_homeassistant_config(get_var(redis, 'ha_yaml_config'))
        remove_var(redis, 'ha_yaml_changed')
        remove_var(redis, 'ha_yaml_config')
        _load_homeassistant_config()

    if ok and get_var(redis, 'chart_config_changed'):
        # HA Configuration changed, and the result is OK, saving it now
        logging.warning('Saving PsychroChart config to disk '
                        '(after producing successfully one chart)')
        save_chart_style(get_var(redis, 'chart_style'))
        save_chart_zones(get_var(redis, 'chart_zones'))
        remove_var(redis, 'chart_config_changed')
        remove_var(redis, 'chart_style')
        remove_var(redis, 'chart_zones')
        _load_chart_config()

    return True
