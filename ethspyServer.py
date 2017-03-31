#!/usr/bin/env python
# coding=utf-8
from flask import *
import sys
import logging
import json

app = Flask(__name__)

@app.route('/ethspy/report/<path:inputs>', methods=['POST'])
def take_report(inputs):
    try:
        print request.data
        data = json.loads(request.data)
        redis = RedisUtil()
        redis.set_obj('report:%s'%inputs, data)
    except Exception, e:
        logging.error('Report error:%s'%str(e))
        abort(401)
    resp = make_response()
    return resp

@app.route('/ethspy/get_report/<path:inputs>')
def get_report(inputs):
    result = []
    redis = RedisUtil()
    keys = redis.keys('report:%s*'%inputs)
    for key in keys:
        v = redis.get_obj(key)
        result.append({'key':key, 'value':v})
        if request.args.get('del', '') != 'no':
            redis.delete(key)
        break
    resp = make_response(json.dumps(result))
    return resp

if __name__ == '__main__':
    port = 5011
    app.run(host='0.0.0.0', port=port, threaded=True)

