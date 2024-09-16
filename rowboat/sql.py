import os

from peewee import OP, Expression, Model, Proxy

from rowboat import ENV
from rowboat.util.psycopgext import Psycopg3ExtDatabase

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
            Psycopg3ExtDatabase(
                "rowboat",
                host="db",
                user="rowboat",
                port=int(os.getenv("PG_PORT", 5432)),
                register_hstore=True
            )
        )
    elif env == "dev":
        database.initialize(
            Psycopg3ExtDatabase(
                "rowboat",
                host="localhost",
                user="postgres",
                password="mysecretpassword",
                port=int(os.getenv("PG_PORT", 5432)),
                register_hstore=True
            )
        )
    else:
        database.initialize(
            Psycopg3ExtDatabase(
                "rowboat", 
                host="172.17.0.1",
                user="rowboat", 
                port=int(os.getenv("PG_PORT", 5432)),
                register_hstore=True
            )
        )

    for model in REGISTERED_MODELS:
        model.create_table(True)

        if hasattr(model, "SQL"):
            database.execute_sql(model.SQL)


def reset_db():
    init_db(ENV)

    for model in REGISTERED_MODELS:
        model.drop_table(True)
        model.create_table(True)
