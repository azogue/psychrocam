#!/usr/bin/env bash

export PORT=7777
export LOGGING_LEVEL="WARNING"
export CUSTOM_PATH="./custom_config"
export REDIS_PWD="customultrasecurepassword"

#IN_RPI=`(uname -a |grep x86| wc -l)`
IN_RPI=`(uname -a |grep armv7l| wc -l)`
IN_RPI_BOOL=`(expr ${IN_RPI})`
if [ "${IN_RPI_BOOL}" = "1" ]
then
    export LABEL=rpi3
else
    export LABEL=x64
fi

echo "--> docker-compose up -d [LABEL:${LABEL}]"
docker-compose up -d