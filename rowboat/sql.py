import os

import psycogreen.gevent
from peewee import OP, Expression, Model, Proxy
from playhouse.postgres_ext import PostgresqlExtDatabase

from rowboat import ENV

psycogreen.gevent.patch_psycopg()

REGISTERED_MODELS = list()

# Create a database proxy we can setup post-init
database = Proxy()

OP["IRGX"] = "irgx"


def pg_regex_i(lhs, rhs):
    return Expression(lhs, OP.IRGX, rhs)


class ModelBase(Model):
    class Meta:
        database = database

    @staticmethod
    def register(cls):
        REGISTERED_MODELS.append(cls)
        return cls


def init_db(env):
    if env == "docker":
        database.initialize(
            PostgresqlExtDatabase(
                "rowboat",
                host="db",
                user="rowboat",
                port=int(os.getenv("PG_PORT", 5432)),
            )
        )
    elif env == "dev":
        database.initialize(
            PostgresqlExtDatabase(
                "rowboat",
                host="localhost",
                user="rowboat",
                port=int(os.getenv("PG_PORT", 5432)),
            )
        )
    else:
        database.initialize(PostgresqlExtDatabase("rowboat", user="rowboat", port=int(os.getenv("PG_PORT", 5432))))

    for model in REGISTERED_MODELS:
        model.create_table(True)

        if hasattr(model, "SQL"):
            database.execute_sql(model.SQL)


def reset_db():
    init_db(ENV)

    for model in REGISTERED_MODELS:
        model.drop_table(True)
        model.create_table(True)
