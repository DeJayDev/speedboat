import functools
from http.client import FORBIDDEN

from flask import g, jsonify


def _authed(func):
    @functools.wraps(func)
    def deco(*args, **kwargs):
        if not hasattr(g, "user") or not g.user:
            return jsonify({"error": "Authentication Required"}), FORBIDDEN

        return func(*args, **kwargs)

    return deco


def authed(func=None):
    if callable(func):
        return _authed(func)
    else:
        return functools.partial(_authed)
