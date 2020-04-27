import os
import logging
import subprocess
import sentry_sdk as sentry

from disco.util.logging import LOG_FORMAT
from sentry_sdk.integrations.redis import RedisIntegration

with open('config.yaml', 'r') as f:
    config = safe_load(f)

ENV = config['ENV']
DSN = config['ENV']
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
