#!/usr/bin/python
# -*- coding: utf-8 -*-
import redis
import datetime
import json
from AlgoCommonLib.WebConfig import *

ENV_TYPE = getEnvType()

class RedisUtil:
    def __init__(self, port=6380):
        if ENV_TYPE == ENV_ONLINE:
            host = '192.168.1.12'
            passwd = None
            db = 0
        else:
            host = '685e545f59634200.m.cnqda.kvstore.aliyuncs.com'
            port = 6379
            passwd = '685e545f59634200:WutongaMINUS1968'
            db = 16
        self.__inst = redis.StrictRedis(host=host, port=port, password=passwd, db=db)

    def get_number(self, key):
        key = str(key)
        if self.__inst.exists(key):
            return int(self.__inst.get(key))
        else:
            self.__inst.set(key, 0)
            return 0
        
    def set_number(self, key, value):
        key = str(key)
        self.__inst.set(key, str(value))
        
    def get_obj(self, key):
        key = str(key)
        if self.__inst.exists(key):
            return json.loads(self.__inst.get(key))
        else:
            return None
        
    def set_obj(self, key, value):
        key = str(key)
        self.__inst.set(key, json.dumps(value))

    def get(self, key):
        return self.__inst.get(key)
    
    def set(self, key, value):
        return self.__inst.set(key, value)

    def keys(self, keys):
        return self.__inst.keys(keys)

    def delete(self, key):
        return self.__inst.delete(key)


if __name__ == '__main__':
    redis = RedisUtil()
    tt = redis.get('ethspy:lastOnlineTime')
    print tt
