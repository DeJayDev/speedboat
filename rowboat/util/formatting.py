from datetime import datetime, timezone
from enum import Enum


class DiscordFormatting(Enum):
    HOUR_MINUTE = "t"
    HOUR_MINUTE_SECOND = "T"
    SHORT_DATE = "d"
    LONG_DATE = "d"
    SHORT_DATE_TIME = "f" # Discord's default
    LONG_DATE_TIME = "F"
    RELATIVE = "R"

    @classmethod
    def __missing__(cls, value):
        return cls.SHORT_DATE_TIME
    
def as_unix(dt: datetime) -> int:
    return int(dt.timestamp(timezone.utc))

def as_discord(dt: datetime, type: DiscordFormatting = DiscordFormatting.SHORT_DATE_TIME) -> str:
    return '<t:{}:{}>'.format(as_unix(dt), type.value)
