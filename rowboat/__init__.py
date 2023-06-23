import logging
from subprocess import check_output

import sentry_sdk as sentry
from disco.util.logging import LOG_FORMAT
from sentry_sdk.integrations.redis import RedisIntegration
from yaml import safe_load

with open("./config.yaml") as config_file:
    config = safe_load(config_file)

ENV = config["ENV"]
REV = check_output(["git", "describe", "--always"]).strip().decode("utf-8")

sentry.init(dsn=config["DSN"], release=REV, environment=ENV, integrations=[RedisIntegration()])

# Log things to file
file_handler = logging.FileHandler("rowboat.log")
log = logging.getLogger()
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
log.addHandler(file_handler)
