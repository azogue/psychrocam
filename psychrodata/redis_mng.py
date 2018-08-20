# -*- coding: utf-8 -*-
"""Very simple wrapper methods around the redis object."""
import json
import pickle

# from psychrocam import redis

from celery import Celery
from redis import StrictRedis

from psychrodata import Config


PREFIX_TYPE_VAR = '_type_var__key_'


def get_celery(main):
    celery_obj = Celery(
        main,
        backend=Config.CELERY_RESULT_BACKEND,
        broker=Config.CELERY_BROKER_URL)
    celery_obj.config_from_object(Config)
    return celery_obj


def get_redis():
    return StrictRedis(
        host=Config.REDIS_HOST, port=Config.REDIS_PORT,
        db=Config.REDIS_DB, password=Config.REDIS_PASSWORD)


def set_var(redis, key, value, expiration=None, pickle_object=False):
    type_value = type(value)
    # print(f'Set var {key}, type: {type_value}')
    # TODO include dt.now() en metadata
    redis.set(PREFIX_TYPE_VAR + key, type_value)
    if isinstance(value, int) or \
            isinstance(value, float) or \
            isinstance(value, bytes):
        redis.set(key, value)
    elif pickle_object:
        redis.set(key, pickle.dumps(value))
    else:
        redis.set(key, json.dumps(value).encode())

    if expiration is not None:
        # if isinstance(expiration, datetime.datetime):
        #     redis.expireat(PREFIX_TYPE_VAR + key, expiration)
        # else:
        redis.expire(PREFIX_TYPE_VAR + key, expiration)


def get_var(redis, key, default=None, unpickle_object=False):
    type_v = redis.get(PREFIX_TYPE_VAR + key)
    value = redis.get(key)

    if type_v is None or value is None:
        return default

    type_v = type_v.decode()
    if 'int' in type_v:
        return int(value)
    elif 'float' in type_v:
        return float(value)
    elif 'bytes' in type_v or 'bool' in type_v:
        return value
    elif unpickle_object:
        return pickle.loads(value)
    else:
        return json.loads(value)


def has_var(redis, key):
    return redis.exists(PREFIX_TYPE_VAR + key) and redis.exists(key)


def remove_var(redis, key):
    redis.delete(key, PREFIX_TYPE_VAR + key)


def get_var_keys(redis, pattern='*'):
    return redis.keys(pattern)


def clean_all_vars(redis):
    all_vars = get_var_keys(redis, pattern=PREFIX_TYPE_VAR + '*')
    if all_vars:
        keys = [k.decode()[len(PREFIX_TYPE_VAR):] for k in all_vars]
        redis.delete(*keys)
