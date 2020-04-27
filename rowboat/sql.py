import os
import psycogreen.gevent; psycogreen.gevent.patch_psycopg()

from peewee import Proxy, OP, Model
from peewee import Expression
from playhouse.postgres_ext import PostgresqlExtDatabase

REGISTERED_MODELS = []

# Create a database proxy we can setup post-init
database = Proxy()

OP['IRGX'] = 'irgx'

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
    database.initialize(PostgresqlExtDatabase(
        'rowboat',
        host='db',
        user='rowboat',
        port=int(os.getenv('PG_PORT', 5432)),
        autorollback=True))

    for model in REGISTERED_MODELS:
        model.create_table(True)

        if hasattr(model, 'SQL'):
            database.execute_sql(model.SQL)
            
def reset_db():
    init_db()

    for model in REGISTERED_MODELS:
        model.drop_table(True)
        model.create_table(True)
