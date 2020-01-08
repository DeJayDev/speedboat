import os
import logging
import subprocess
import sentry_sdk as sentry

from disco.util.logging import LOG_FORMAT
from sentry_sdk.integrations.redis import RedisIntegration

ENV = os.getenv('ENV', 'local')
DSN = os.getenv('DSN')
REV = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip()

VERSION = '1.5.0'

sentry.init(
    dsn=DSN,
    release=REV,
    environment=ENV,
    integrations=[RedisIntegration()]
)

# Log things to file
file_handler = logging.FileHandler('rowboat.log')
log = logging.getLogger()
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
log.addHandler(file_handler)
