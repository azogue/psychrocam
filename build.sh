#!/usr/bin/env bash

export DOCKER_ID_USER=azogue
export COMPOSE_PROJECT_NAME=psychrowebcam
export PORT=7654
export LOGGING_LEVEL="INFO"
export CUSTOM_PATH="./custom_config"
export REDIS_PWD="ultrasecurepassword"

export LABEL=x86
echo "--> [`(date '+%Y-%m-%d %H:%M:%S')`] docker-compose build --build-arg label=${LABEL} psychrocam"
docker-compose build --build-arg label=${LABEL} psychrocam
echo "* End build: `(date '+%Y-%m-%d %H:%M:%S')`"

export LABEL=rpi3_slim
echo "--> [`(date '+%Y-%m-%d %H:%M:%S')`] docker-compose build --build-arg label=${LABEL} psychrocam"
docker-compose build --build-arg label=${LABEL} psychrocam
echo "* End build: `(date '+%Y-%m-%d %H:%M:%S')`"


export LABEL=x86
echo "--> [`(date '+%Y-%m-%d %H:%M:%S')`] PUSH IMAGES: docker push ${DOCKER_ID_USER}/psychrocam:${LABEL}"
docker push ${DOCKER_ID_USER}/psychrocam:${LABEL}
echo "* End push: `(date '+%Y-%m-%d %H:%M:%S')`"

export LABEL=rpi3_slim
echo "--> [`(date '+%Y-%m-%d %H:%M:%S')`] PUSH IMAGES: docker push ${DOCKER_ID_USER}/psychrocam:${LABEL}"
docker push ${DOCKER_ID_USER}/psychrocam:${LABEL}
echo "* End push: `(date '+%Y-%m-%d %H:%M:%S')`"


