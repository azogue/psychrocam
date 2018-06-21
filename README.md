# psychrocam - A flask API for serving `psychrochart` SVG files like a webcam

![HA View](https://github.com/azogue/psychrocam/blob/master/screenshots/svgchart.svg?raw=true)

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

# Use one or the other depending on your host:
# export LABEL="x86"
export LABEL="rpi3_slim"

docker-compose up -d
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
  Outside:
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

## TODO

- Change the way it access to the Home Assistant event stream.
- Convert this in a HASS.io addon or a HA component
- Use a better UI in HA (Lovelace future?)
- Use sun position and orientations to predict irradiation power (ASHRAE clear sky model) for windows and walls and publish new HA sensors