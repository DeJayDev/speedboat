import time

from contextlib import contextmanager
from datadog import statsd


def to_tags(obj=None, **kwargs):
    if obj:
        kwargs.update(obj)
    return ['{}:{}'.format(k, v) for k, v in list(kwargs.items())]


@contextmanager
def timed(metric, tags=None):
    start = time.time()
    try:
        yield
    except:
        raise
    finally:
        if tags and isinstance(tags, dict):
            tags = to_tags(tags)
        statsd.timing(metric, (time.time() - start) * 1000, tags=tags)
