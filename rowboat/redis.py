import os
import json

import redis

ENV = os.getenv('ENV', 'local')

rdb = redis.Redis(db=0, host='redis')

def emit(typ, **kwargs):
    kwargs['type'] = typ
    rdb.publish('actions', json.dumps(kwargs))

