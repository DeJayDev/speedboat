from datetime import datetime, timezone

from peewee import BigIntegerField, CompositeKey, DateTimeField, IntegerField, TextField

from rowboat.sql import ModelBase


@ModelBase.register
class Tag(ModelBase):
    guild_id = BigIntegerField()
    author_id = BigIntegerField()

    name = TextField()
    content = TextField()
    times_used = IntegerField(default=0)

    created_at = DateTimeField(default=datetime.now(timezone.utc))

    class Meta:
        table_name = 'tags'
        primary_key = CompositeKey('guild_id', 'name')
