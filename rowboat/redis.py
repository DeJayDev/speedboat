import json

import redis

from rowboat import ENV

rdb = redis.Redis(db=0)


def emit(typ, **kwargs):
    kwargs['type'] = typ
    rdb.publish('actions', json.dumps(kwargs))
