import math
from datetime import datetime, timedelta

from disco.bot.command import CommandError

UNITS = {
    "s": lambda v: v,
    "m": lambda v: v * 60,
    "h": lambda v: v * 60 * 60,
    "d": lambda v: v * 60 * 60 * 24,
    "w": lambda v: v * 60 * 60 * 24 * 7,
    "y": lambda v: v * 60 * 60 * 24 * 365,
}


def parse_duration(raw, source=None, negative=False, safe=False):
    if not raw:
        if safe:
            return None
        raise CommandError("Invalid duration")

    value = 0
    digits = ""

    for char in raw:
        if char.isdigit():
            digits += char
            continue

        if char not in UNITS or not digits:
            if safe:
                return None
            raise CommandError("Invalid duration")

        value += UNITS[char](int(digits))
        digits = ""

    if negative:
        value = value * -1

    if value > 999999999:  # Fixes SPEEDBOAT-60 on Sentry
        raise CommandError("Invalid duration")

    return (source or datetime.utcnow()) + timedelta(seconds=value + 1)


def human_time(time):
    secs = float(time.total_seconds())

    units = [("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1)]
    parts = list()

    for unit, mul in units:
        if secs / mul >= 1 or mul == 1:
            if mul > 1:
                length = int(math.floor(secs / mul))
                secs -= length * mul
            else:
                length = int(secs) if secs != int(secs) else int(secs)
            parts.append("{} {}{}".format(length, unit, "" if length == 1 else "s"))

    return ", ".join(parts)
