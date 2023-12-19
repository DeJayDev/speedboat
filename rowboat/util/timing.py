from time import time

import gevent
from gevent.lock import Semaphore

from rowboat.util.time import timestamp_now, as_unix


class Eventual(object):
    """
    A function that will be triggered eventually.
    """

    def __init__(self, func):
        self.func = func
        self._next = None
        self._t = None

    def wait(self, nxt):
        def f():
            wait_time = self._next - timestamp_now()
            gevent.sleep(wait_time)
            self._next = None
            gevent.spawn(self.func)

        if self._t:
            self._t.kill()

        self._next = nxt
        self._t = gevent.spawn(f)

    def trigger(self):
        if self._t:
            self._t.kill()
        self._next = None
        gevent.spawn(self.func)

    def set_next_schedule(self, date):
        date = as_unix(date)
        if date < timestamp_now():
            return gevent.spawn(self.trigger)

        if not self._next or date < self._next:
            self.wait(date)


class Debounce(object):
    def __init__(self, func, default, hardlimit, **kwargs):
        self.func = func
        self.default = default
        self.hardlimit = hardlimit
        self.kwargs = kwargs

        self._start = time()
        self._lock = Semaphore()
        self._t = gevent.spawn(self.wait)

    def active(self):
        return self._t is not None

    def wait(self):
        gevent.sleep(self.default)

        with self._lock:
            self.func(**self.kwargs)
            self._t = None

    def touch(self):
        if self._t:
            with self._lock:
                if self._t:
                    self._t.kill()
                    self._t = None
        else:
            self._start = time()

        if time() - self._start > self.hardlimit:
            gevent.spawn(self.func, **self.kwargs)
            return

        self._t = gevent.spawn(self.wait)
