# -*- coding: utf-8 -*-
import logging
import os

import yaml


###############################################################################
# PATHS
###############################################################################
basedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static')
HA_CONFIG_DEFAULT = os.path.join(basedir, 'default_ha_sensors.yaml')
HA_CONFIG_CUSTOM = os.path.join(basedir, '_custom_ha_sensors.yaml')

CHART_STYLE_DEFAULT = os.path.join(basedir, 'default_chart_style.yaml')
CHART_STYLE_CUSTOM = os.path.join(basedir, '_custom_chart_style.yaml')
CHART_ZONES_DEFAULT = os.path.join(basedir, 'default_zones_overlay.yaml')
CHART_ZONES_CUSTOM = os.path.join(basedir, '_custom_zones_overlay.yaml')

###############################################################################
# Common methods
###############################################################################
PARAMS_DUMP_HA = dict(allow_unicode='UTF-8', encoding='UTF-8',
                      default_flow_style=False)
PARAMS_DUMP = dict(allow_unicode='UTF-8', encoding='UTF-8')


def _select(custom_path, default_path):
    if os.path.exists(custom_path):
        return custom_path
    return default_path


def _load_yaml_config(file_path):
    with open(file_path) as f:
        yaml_config = yaml.load(f)
    logging.debug(f"YAML config keys: {yaml_config.keys()}")
    return yaml_config


def _save_custom_yaml_config(new_config, file_path, **params):
    if isinstance(new_config, dict) and new_config:
        yaml_bytes = yaml.dump(new_config, **params)
        with open(file_path, 'wb') as f:
            f.write(yaml_bytes)
        logging.info(f"YAML config:\n{yaml_bytes.decode()}")
        return True
    logging.error(f"Not saved! BAD YAML config: {new_config}")
    return False


###############################################################################
# CONFIG YAML FILES
###############################################################################
def load_homeassistant_config():
    return _load_yaml_config(_select(HA_CONFIG_CUSTOM, HA_CONFIG_DEFAULT))


def save_homeassistant_config(new_config):
    return _save_custom_yaml_config(new_config,
                                    HA_CONFIG_CUSTOM, **PARAMS_DUMP_HA)


def load_chart_styles():
    return _load_yaml_config(_select(CHART_STYLE_CUSTOM, CHART_STYLE_DEFAULT))


def save_chart_style(new_config):
    return _save_custom_yaml_config(new_config,
                                    CHART_STYLE_CUSTOM, **PARAMS_DUMP)


def load_chart_zones():
    return _load_yaml_config(_select(CHART_ZONES_CUSTOM, CHART_ZONES_DEFAULT))


def save_chart_zones(new_config):
    return _save_custom_yaml_config(new_config,
                                    CHART_ZONES_CUSTOM, **PARAMS_DUMP)
