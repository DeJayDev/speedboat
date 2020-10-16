import gevent


def wait_many(*args, **kwargs):
    def _async():
        for awaitable in args:
            awaitable.wait()

    gevent.spawn(_async).get(timeout=kwargs.get('timeout', None))

    if kwargs.get('track_exceptions', True):
        from rowboat import sentry
        for awaitable in args:
            if awaitable.exception:
                sentry.capture_exception(exc_info=awaitable.exc_info)
