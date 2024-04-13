import json

import redis

from rowboat import ENV

if ENV == "docker":
    rdb = redis.Redis(db=0, host="keydb")
else:
    rdb = redis.Redis(db=0, host="172.17.0.1")


def emit(typ, **kwargs):
    kwargs["type"] = typ
    rdb.publish("actions", json.dumps(kwargs))
