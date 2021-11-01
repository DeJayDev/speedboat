import logging
import os
import subprocess

import sentry_sdk as sentry
from disco.util.logging import LOG_FORMAT
from sentry_sdk.integrations.redis import RedisIntegration
from yaml import safe_load

# Please tell me how to fix this
with open(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir) + '/config.yaml')) as f:
    config = safe_load(f)

ENV = config['ENV']
DSN = config['DSN']
REV = str(subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip())

VERSION = f'1.9+{REV}'  # Ladies and gentlemen the only place I will use an fstring.

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
