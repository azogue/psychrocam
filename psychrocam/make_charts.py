# -*- coding: utf-8 -*-
import datetime as dt
from io import BytesIO
import logging

import numpy as np
from scipy.spatial import ConvexHull

from psychrochart.chart import PsychroChart, load_config
from psychrochart.equations import (
    humidity_ratio, saturation_pressure_water_vapor)
from psychrocam.redis_mng import get_var, set_var


###############################################################################
# PSYCHROCHART SVG GENERATION
###############################################################################
def append_convex_hull_zones(chart, groups, points):
    for convex_hull_zone, style_line, style_fill in groups:
        int_points = np.array(
            [(point['xy'][0],
              1000 * humidity_ratio(saturation_pressure_water_vapor(
                  point['xy'][0]) * point['xy'][1] / 100.,
                                    chart.p_atm_kpa))
             for name, point in points.items() if name in convex_hull_zone])

        if len(int_points) < 3:
            continue

        hull = ConvexHull(int_points)
        # noinspection PyUnresolvedReferences
        for simplex in hull.simplices:
            chart._handlers_annotations.append(
                chart.axes.plot(int_points[simplex, 0],
                                int_points[simplex, 1], **style_line))
        chart._handlers_annotations.append(
            chart.axes.fill(int_points[hull.vertices, 0],
                            int_points[hull.vertices, 1], **style_fill))


def make_psychrochart(altitude=None, pressure_kpa=None,
                      points=None, connectors=None,
                      arrows=None, interior_zones=None):
    """Create the PsychroChart SVG file and save it to disk."""
    # Load chart style:
    chart_style = load_config(get_var('chart_style'))
    zones = get_var('chart_zones')

    if altitude is None:  # Try redis key
        altitude = get_var('altitude')
    if pressure_kpa is None:  # Try redis key
        pressure_kpa = get_var('pressure_kpa')
    if points is None:  # Try redis key
        points = get_var('last_points', default={})
    if arrows is None:  # Try redis key
        arrows = get_var('arrows')
    if interior_zones is None:  # Try redis key
        interior_zones = get_var('interior_zones')

    p_label = ''
    if pressure_kpa is not None:
        chart_style['limits']['pressure_kpa'] = pressure_kpa
        p_label = 'P={:.1f} mb '.format(pressure_kpa * 10)
        chart_style['limits'].pop('altitude_m', None)
        logging.debug(f"using pressure: {pressure_kpa}")
    elif altitude is not None:
        chart_style['limits']['altitude_m'] = altitude
        p_label = 'H={:.0f} m '.format(altitude)

    # Make chart
    # chart = PsychroChart(chart_style, zones, logger=app.logger)
    chart = PsychroChart(chart_style, zones)

    # Append lines
    t_min, t_opt, t_max = 16, 23, 30
    chart.plot_vertical_dry_bulb_temp_line(
        t_min, {"color": [0.0, 0.125, 0.376], "lw": 2, "ls": ':'},
        ' TOO COLD, {:g}°C'.format(t_min), ha='left',
        loc=0., fontsize=14)
    chart.plot_vertical_dry_bulb_temp_line(
        t_opt, {"color": [0.475, 0.612, 0.075], "lw": 2, "ls": ':'})
    chart.plot_vertical_dry_bulb_temp_line(
        t_max, {"color": [1.0, 0.0, 0.247], "lw": 2, "ls": ':'},
        'TOO HOT, {:g}°C '.format(t_max), ha='right', loc=1,
        reverse=True, fontsize=14)

    # Append pressure / altitude label
    if p_label:
        chart.axes.annotate(
            p_label, (1, 0), xycoords='axes fraction', ha='right', va='bottom',
            fontsize=15, color='darkviolet')

    if arrows:
        chart.plot_arrows_dbt_rh(arrows)
        # Append history label
        points_dq = get_var('deque_points', default=[], unpickle_object=True)
        if len(points_dq) > 2:
            start = list(points_dq[0].values())[0]
            end = list(points_dq[-1].values())[0]
            delta = (dt.datetime.fromtimestamp(end['ts'])
                     - dt.datetime.fromtimestamp(start['ts'])).total_seconds()
            # delta = history_config['delta_arrows']
            chart.axes.annotate(
                '∆T:{:.1f}h'.format(delta / 3600.),
                (0, 0), xycoords='axes fraction', ha='left', va='bottom',
                fontsize=10, color='darkgrey')

    if points:
        # TODO fix interior_zones type
        # chart.plot_points_dbt_rh(
        #     points, connectors,
        #     [k for k in interior_zones if k in points])
            # list(filter(lambda x: x in points, interior_zones)))
        # elif points:
        if interior_zones is not None:
            append_convex_hull_zones(chart, interior_zones, points)

        chart.plot_points_dbt_rh(points, connectors)

    chart.plot_legend(
        frameon=False, fontsize=8, labelspacing=.8, markerscale=.7)

    bytes_svg = BytesIO()
    chart.save(bytes_svg, format='svg')
    bytes_svg.seek(0)
    set_var('svg_chart', bytes_svg.read())
    set_var('chart_axes', chart.axes, pickle_object=True)

    chart.remove_annotations()
    set_var('chart', chart, pickle_object=True)

    return True
