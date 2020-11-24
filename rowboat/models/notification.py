import json
from datetime import datetime

import arrow
from holster.enum import Enum
from peewee import IntegerField, DateTimeField
from playhouse.postgres_ext import BinaryJSONField, BooleanField

from rowboat.redis import rdb
from rowboat.sql import ModelBase

NotificationTypes = Enum(
    GENERIC=1,
    CONNECT=2,
    RESUME=3,
    GUILD_JOIN=4,
    GUILD_LEAVE=5,
)


@ModelBase.register
class Notification(ModelBase):
    Types = NotificationTypes

    type_ = IntegerField(column_name='type')
    metadata = BinaryJSONField(default={})
    read = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = 'notifications'

        indexes = (
            (('created_at', 'read'), False),
        )

    @classmethod
    def get_unreads(cls, limit=25):
        return cls.select().where(
            cls.read == 0,
        ).order_by(
            cls.created_at.asc()
        ).limit(limit)

    @classmethod
    def dispatch(cls, typ, **kwargs):
        obj = cls.create(
            type_=typ,
            metadata=kwargs
        )

        rdb.publish('notifications', json.dumps(obj.to_user()))
        return obj

    def to_user(self):
        data = {'id': self.id, 'date': arrow.get(self.created_at).humanize()}

        if self.type_ == self.Types.GENERIC:
            data['title'] = self.metadata.get('title', 'Generic Notification')
            data['content'] = self.metadata.get('content', '').format(m=self.metadata)
        elif self.type_ == self.Types.CONNECT:
            data['title'] = '{} connected'.format(
                'Production' if self.metadata['env'] == 'prod' else 'Testing')
            data['content'] = self.metadata.get('content', '').format(m=self.metadata)
        elif self.type_ == self.Types.RESUME:
            data['title'] = '{} resumed'.format(
                'Production' if self.metadata['env'] == 'prod' else 'Testing')
            data['content'] = self.metadata.get('content', '').format(m=self.metadata)

        return data
