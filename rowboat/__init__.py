import os
import logging
import subprocess
import sentry_sdk as sentry

from disco.util.logging import LOG_FORMAT
from sentry_sdk.integrations.redis import RedisIntegration
from yaml import safe_load

with open(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir) + '/config.yaml')) as f: # Please tell me how to fix this
    config = safe_load(f)

ENV = config['ENV']
DSN = config['DSN']
REV = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip()

VERSION = '1.6.1'

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
