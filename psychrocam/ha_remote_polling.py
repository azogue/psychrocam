# -*- coding: utf-8 -*-
"""Extract sensor values from a remote Home Assistant instance."""
from collections import deque
import datetime as dt
import logging

from homeassistant import remote
from homeassistant.exceptions import HomeAssistantError
import matplotlib.colors as mcolors
from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError, MaxRetryError

from psychrocam.redis_mng import get_var, set_var, has_var, remove_var


###############################################################################
# HA Config
###############################################################################
def parse_config_ha(yaml_config):
    location_config = yaml_config['location']
    if 'altitude' in location_config:
        set_var('altitude', location_config['altitude'])
    if 'pressure_sensor' in location_config:
        set_var('pressure_sensor', location_config['pressure_sensor'])

    history_config = yaml_config['history']
    set_var('ha_history', history_config)

    # Get HA sensors
    interior_sensors = yaml_config['interior']
    exterior_sensors = yaml_config['exterior']

    # TODO config option to define convex hull zones and its styling
    if interior_sensors:  # convex hull zones with interior / exterior sensors
        '''
        interior_zones = [
            ([sensor_key1, sensor_key2, ...],       # list of points
             {"color": 'darkgreen', "lw": 0, ...},  # line style
             {"color": 'darkgreen', "lw": 0, ...}),  # filling style
        ]
        '''
        interior_zones = [
            (list(interior_sensors.keys()),
             dict(color='darkgreen', lw=2, alpha=.5, ls=':'),
             dict(color='darkgreen', lw=0, alpha=.3)),
            (list(exterior_sensors.keys()),
             dict(color='darkblue', lw=1, alpha=.5, ls='--'),
             dict(color='darkblue', lw=0, alpha=.3)),
        ]
        set_var('interior_zones', interior_zones)

    # TODO implement sun position and irradiations
    # sun_sensor = yaml_config['sun']
    # print(sun_sensor)
    sensors = {}
    if interior_sensors:
        sensors.update({"interior": interior_sensors})
    if exterior_sensors:
        sensors.update({"exterior": exterior_sensors})
    if 'pressure_sensor' in location_config:
        sensors.update({"pressure_sensor": location_config['pressure_sensor']})
    # if sun_sensor:
    #     sensors.update({"sun": sun_sensor})

    if sensors:
        set_var('ha_sensors', sensors)

    # Get HA API
    ha_config = yaml_config['homeassistant']
    set_var('ha_config', ha_config)

    set_var('ha_yaml_config', yaml_config)


###############################################################################
# HA remote polling
###############################################################################
def get_ha_api():
    ha_config = get_var('ha_config')
    logging.debug(f"HA API config: {ha_config}")

    # Get HA API
    api_params = dict(host=ha_config.get('host', '127.0.0.1'),
                      api_password=ha_config.get('api_password', None),
                      port=ha_config.get('port', 8123),
                      use_ssl=ha_config.get('use_ssl', False))
    try:
        api = remote.API(**api_params)
        try:
            assert api.validate_api(force_validate=True)
            set_var('ha_api', api, pickle_object=True)
        except AssertionError:
            logging.error(f"No HA API found. Removing config from cache")
            if has_var('ha_api'):
                remove_var('ha_api')
    except (remote.HomeAssistantError, ConnectionError,
            NewConnectionError, MaxRetryError) as exc:
        logging.error(f"{exc.__class__}: {str(exc)}")
        return


def get_states():
    api = get_var('ha_api', unpickle_object=True)
    if not api:
        logging.error(f"No HA API loaded, aborting get_states")
        if has_var('ha_states'):
            remove_var('ha_states')
        return {}

    sensors = get_var('ha_sensors')
    logging.debug(f"Sensors: {sensors}")
    entities = []
    if "pressure_sensor" in sensors:
        entities.append(sensors["pressure_sensor"])
    # if "sun" in sensors:
    #     entities.append(sensors["sun"])

    if "interior" in sensors:
        entities += [s for sensor in sensors["interior"].values()
                     for k, s in sensor.items()
                     if k in ['temperature', 'humidity']]
    if "exterior" in sensors:
        entities += [s for sensor in sensors["exterior"].values()
                     for k, s in sensor.items()
                     if k in ['temperature', 'humidity']]
    # print(entities)
    try:
        states = {s.entity_id: s.as_dict()
                  for s in filter(lambda x: x.entity_id in entities,
                                  remote.get_states(api))}
        set_var('ha_states', states, pickle_object=True)
    except (HomeAssistantError,
            ConnectionRefusedError,
            remote.HomeAssistantError):
        states = {}

    return states


def _arrow_style(style):
    if 'color' in style:
        color = style['color']
        if isinstance(color, str) and mcolors.is_color_like(color):
            color = list(mcolors.to_rgb(color))
        else:
            color = list(color)
    else:
        color = [1, .8, 0.1]
    if 'alpha' in style:
        color += [style['alpha']]
    elif len(color) == 3:
        color += [.6]
    return {"color": color, "arrowstyle": 'wedge'}


def _mb2kpa(pressure_mb):
    return pressure_mb / 10.


def _make_ev_data(first_point, mid_point, end_point):
    def _make_delta(start, end):
        ts_f = dt.datetime.fromtimestamp(end['ts'])
        ts_0 = dt.datetime.fromtimestamp(start['ts'])
        delta_ts = (ts_f - ts_0).total_seconds()
        if delta_ts == 0:
            delta_ts = 3600
            logging.debug(f"Error ∆t=0: {ts_0, ts_f}")
        delta_temp = end['xy'][0] - start['xy'][0]
        return {
            '∆t [min]': round(delta_ts / 60, 1),
            '∆T [°C]': round(delta_temp, 1),
            '∆HR [%]': round(end['xy'][1] - start['xy'][1], 1),
            '∆T [°C/h]': round(delta_temp / (delta_ts / 3600), 3),
            'T [°C]': start['xy'][0],
            'HR [%]': start['xy'][1],
            'ts': ts_0.isoformat()
        }

    out = {
        "last": {
            'T [°C]': mid_point['xy'][0],
            'HR [%]': mid_point['xy'][1]}
    }

    if first_point:
        out['first'] = _make_delta(first_point, end_point)
    if mid_point:
        out['mid'] = _make_delta(mid_point, end_point)

    return out


def make_points_from_states(states):
    # Make points
    sensors = get_var('ha_sensors')
    points = get_var('last_points', default={})
    points_unknown = get_var('points_unknown', default=[])

    for sensor_group in sensors.values():
        if isinstance(sensor_group, str):
            try:
                set_var('pressure_kpa',
                        _mb2kpa(float(states[sensor_group]['state'])))
            except ValueError:
                logging.error(f"Bad pressure read from {sensor_group}")
                # pass
            continue
        for key, p_config in sensor_group.items():
            try:
                points.update(
                    {key: {'xy': (
                        float(states[p_config['temperature']]['state']),
                        float(states[p_config['humidity']]['state'])),
                           'style': {'marker': 'o', **p_config['style']},
                           'ts': (states[p_config['humidity']]['last_updated']
                                  .timestamp()),
                           'label': key}})
                if key in points_unknown:
                    points_unknown.remove(key)
            except KeyError:
                logging.error(
                    f"KeyError with {key} [sensor_group: {sensor_group}]")
                points_unknown.append(key)
            except ValueError:
                logging.warning(
                    f"ERROR with {key} sensor [state: "
                    f"{states[p_config['temperature']]['state']}ºC, "
                    f"{states[p_config['humidity']]['state']}%]")
                points_unknown.append(key)
    set_var('last_points', points)
    set_var('points_unknown', points_unknown)

    # Make arrows
    history_config = get_var('ha_history', default={})
    if 'delta_arrows' not in history_config or \
            not history_config['delta_arrows']:
        return

    delta_arrows = history_config['delta_arrows']
    scan_interval = history_config['scan_interval']
    len_deque = max(3, int(delta_arrows / scan_interval))
    points_dq = get_var('deque_points',
                        default=deque([], maxlen=len_deque),
                        unpickle_object=True)
    points_dq.append(points)
    set_var('deque_points', points_dq, pickle_object=True)

    num_points_dq = len(points_dq)
    if num_points_dq > 1:
        # arrows = {k: [p['xy'], points_dq[0][k]['xy']]
        #           for k, p in points.items() if k in points_dq[0]
        #           and p != points_dq[0][k]}
        arrows = {k: {'xy': [p['xy'], points_dq[0][k]['xy']],
                      'style': _arrow_style(p['style'])}
                  for k, p in points.items() if k in points_dq[0]
                  and p != points_dq[0][k]}
        # logging.info('MAKE ARROWS: %s', arrows)
        set_var('arrows', arrows)

    # Make evolution JSON endpoint with history
    if num_points_dq > 3:
        ev_data = {
            "num_points": num_points_dq,
            "pressure_kPa": get_var('pressure_kpa')}

        start_p = points_dq[0]
        mid_p = points_dq[num_points_dq // 2 - 1]
        end_p = points_dq[-1]
        ev_data.update(
            {key: _make_ev_data(start_p.get(key), mid_p.get(key), point)
             for key, point in end_p.items()})
        logging.debug(f"EVOLUTION_DATA: {ev_data}")
        set_var('ha_evolution', ev_data)
