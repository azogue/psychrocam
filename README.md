# psychrocam - A flask API for serving `psychrochart` SVG files like a webcam

<img src="https://rawgit.com/azogue/psychrocam/master/screenshots/svgchart.svg" width="100%" height="100%">

## Description

**Psychrocam** is a _flask-celery-redis_ backend to create SVG [psychrometric charts](https://github.com/azogue/psychrochart) and overlay information from [Home Assistant](https://www.home-assistant.io) temperature and humidity sensors.
The main objective is to create a fake 'webcam' to add it as a Home Assistant [generic camera](https://www.home-assistant.io/components/camera.generic/), showing the psychrometric state in real-time.

![HA View](https://github.com/azogue/psychrocam/blob/master/screenshots/ha_screenshot.png?raw=true)

This little project consist in 2 docker containers running:
- A Redis database.
- The main container, running supervisor to execute:
  * A celery worker
  * The celery beat, sending update tasks every `scan_interval` seconds
  * Gunicorn serving the flask application

## Use with docker

The quickest way to get things running, just git clone this repository and run `. run_compose.sh` (notice the space between `.` and the script name, needed to preserve the exports).

You can edit that script to change the environment variables needed to run the container, or export them and run manually:

```
export PORT=7777
export LOGGING_LEVEL=WARNING
export CUSTOM_PATH="./custom_config"
export REDIS_PWD="customultrasecurepassword"

# Use one or the other depending on your host architecture:
# export LABEL=x64
export LABEL=rpi3

# Pull the container from docker hub:
docker pull azogue/psychrocam:${LABEL}
docker-compose up -d

# Or build it
docker-compose up -d --build
```

## Customize

To get access to HomeAssistant and its sensors you need to write your own `custom_config/custom_ha_sensors.yaml`, with this schema:

```yaml
homeassistant:
  api_password: yourultrasecurehapassword
  host: 192.168.1.33
  port: 8123
  use_ssl: False

history:
  delta_arrows: 10800  # seconds (:= 3h)
  scan_interval: 30

location:
  altitude: 7
  # Optional pressure sensor to adapt atmospheric pressure:
  pressure_sensor: sensor.pressure_mb

# Interior sensor pairs
interior:
  Office:
    humidity: sensor.sensor_office_humidity
    style:
      alpha: 0.9
      color: '#8FBB46'
      markersize: 12
    temperature: sensor.sensor_office_temperature
  Living room:
    humidity: sensor.sensor_livingroom_humidity
    style:
      alpha: 0.9
      color: darkorange
      markersize: 12
    temperature: sensor.sensor_livingroom_temperature

# Exterior sensor pairs
exterior:
  Terraza:
    humidity: sensor.sensor_terraza_humidity
    style:
      alpha: 0.7
      color: '#5882FB'
      markersize: 12
    temperature: sensor.sensor_terraza_temperature
  Predicted:
    temperature: sensor.dark_sky_temperature
    humidity: sensor.dark_sky_humidity
    style:
      alpha: 0.6
      color: '#7996BB'
      markersize: 7
```

And go to [host:7777/svgchart](http://0.0.0.0:7777/svgchart) to show the last SVG psychrometric chart, or check [/ha_states](http://0.0.0.0:7777/ha_states), [/ha_config](http://0.0.0.0:7777/ha_config) and [/chartconfig](http://0.0.0.0:7777/chartconfig).

## Home Assistant integration

To see your psychrometric data in Home Assistant, add this generic camera:

```yaml
homeassistant:
  customize:
    camera.psychrometric_chart:
      friendly_name: Diagrama psicrométrico

camera:
  - platform: generic
    name: psychrometric_chart
    still_image_url: http://192.168.1.33:7777/svgchart
    content_type: 'image/svg+xml'
```

You can add extra sensors to HA based on the evolution of watched states, that are present in other routes of this API (_this is a work in progress_).

In `/ha_evolution` you can access this JSON data:

```json
{
  "Office": {
    "first": {
      "HR [%]": 42.2,
      "T [°C]": 25.6,
      "ts": "2018-06-21T07:11:19.575077",
      "∆HR [%]": -0.2,
      "∆T [°C/h]": 0.766,
      "∆T [°C]": 2.3,
      "∆t [min]": 180.2
    },
    "last": {
      "HR [%]": 40.8,
      "T [°C]": 26.1
    },
    "mid": {
      "HR [%]": 40.8,
      "T [°C]": 26.1,
      "ts": "2018-06-21T08:41:06.489618",
      "∆HR [%]": 1.2,
      "∆T [°C/h]": 1.195,
      "∆T [°C]": 1.8,
      "∆t [min]": 90.4
    }
  },
  ... ,
  "Terraza": {
    "first": {
      "HR [%]": 41.8,
      "T [°C]": 26.9,
      "ts": "2018-06-21T07:11:31.281293",
      "∆HR [%]": -0.7,
      "∆T [°C/h]": 1.001,
      "∆T [°C]": 3.0,
      "∆t [min]": 179.9
    },
    "last": {
      "HR [%]": 24.3,
      "T [°C]": 37.1
    },
    "mid": {
      "HR [%]": 24.3,
      "T [°C]": 37.1,
      "ts": "2018-06-21T08:41:24.038771",
      "∆HR [%]": 16.8,
      "∆T [°C/h]": -4.8,
      "∆T [°C]": -7.2,
      "∆t [min]": 90.0
    }
  },
  "num_points": 720,
  "pressure_kPa": 101.71
}

```


An example of integration would be adding some sensors showing the temperature rate change (to use them in automations). This can be done with a REST sensor and some template sensors exploiting its attributes:

```yaml
homeassistant:
  customize:
    sensor.psychrometric_evolution:
      hidden: True
  customize_glob:
    sensor.temp_change_*:
      icon: mdi:delta

sensor:
  - platform: rest
    name: psychrometric_evolution
    resource: http://192.168.1.33:7777/ha_evolution
    unit_of_measurement: "sample"
    json_attributes:
      - pressure_kPa
      - Office
      - Salón
      - Terraza
    scan_interval: 30
    value_template: '{{ value_json.num_points | int }}'

  - platform: template
    sensors:
      temp_change_office:
        friendly_name: '∆T Office'
        value_template: '{% if "Office" in states.sensor.psychrometric_evolution.attributes %}{{ states.sensor.psychrometric_evolution.attributes["Office"]["first"]["∆T [°C/h]"] | round(2)  }}{% endif %}'
        unit_of_measurement: '°C/h'
      temp_change_livingroom:
        friendly_name: '∆T Salón'
        value_template: '{% if "Salón" in states.sensor.psychrometric_evolution.attributes %}{{ states.sensor.psychrometric_evolution.attributes["Salón"]["first"]["∆T [°C/h]"] | round(2) }}{% endif %}'
        unit_of_measurement: '°C/h'
      temp_change_terraza:
        friendly_name: '∆T Terraza'
        value_template: '{% if "Terraza" in states.sensor.psychrometric_evolution.attributes %}{{ states.sensor.psychrometric_evolution.attributes["Terraza"]["first"]["∆T [°C/h]"] | round(2) }}{% endif %}'
        unit_of_measurement: '°C/h'
```

## TODO

- Change the way it access to the Home Assistant event stream.
- Convert this in a HASS.io addon or a HA component
- Use a better UI in HA (Lovelace future?)
- Use sun position and orientations to predict irradiation power (ASHRAE clear sky model) for windows and walls and publish new HA sensors