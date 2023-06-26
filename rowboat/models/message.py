import json
import re
import traceback
import uuid
from datetime import datetime, timedelta

from peewee import (BigIntegerField, BooleanField, DateTimeField,
                    ForeignKeyField, TextField, UUIDField)
from playhouse.postgres_ext import ArrayField, BinaryJSONField

from rowboat import REV
from rowboat.constants import WEB_URL
from rowboat.models.user import User
from rowboat.sql import ModelBase
from rowboat.util import default_json

EMOJI_RE = re.compile(r'<:.+:([0-9]+)>')


@ModelBase.register
class Message(ModelBase):
    id = BigIntegerField(primary_key=True)
    channel_id = BigIntegerField()
    guild_id = BigIntegerField(null=True)
    author = ForeignKeyField(User)
    content = TextField()
    timestamp = DateTimeField()
    edited_timestamp = DateTimeField(null=True, default=None)
    deleted = BooleanField(default=False)
    num_edits = BigIntegerField(default=0)
    command = TextField(null=True)

    mentions = ArrayField(BigIntegerField, default=[], null=True)
    emojis = ArrayField(BigIntegerField, default=[], null=True)
    attachments = ArrayField(TextField, default=[], null=True)
    embeds = BinaryJSONField(default=[], null=True)

    SQL = '''
        CREATE INDEX\
                IF NOT EXISTS messages_content_fts ON messages USING gin(to_tsvector('english', content));
        CREATE INDEX\
                IF NOT EXISTS messages_mentions ON messages USING gin (mentions);
    '''

    class Meta:
        table_name = 'messages'

        indexes = (
            # These indexes are mostly just general use
            (('channel_id', ), False),
            (('guild_id', ), False),
            (('deleted', ), False),

            # Timestamp is regularly sorted on
            (('timestamp', ), False),

            # Some queries want to get history in a guild or channel
            (('author', 'guild_id', 'channel_id'), False),
        )

    @classmethod
    def from_disco_message_update(cls, obj):
        if not obj.edited_timestamp:
            return

        to_update = {
            'edited_timestamp': obj.edited_timestamp,
            'num_edits': cls.num_edits + 1,
            'mentions': list(obj.mentions.keys()),
        }

        if obj.content is not None:
            to_update['content'] = obj.with_proper_mentions
            to_update['emojis'] = list(map(int, EMOJI_RE.findall(obj.content)))

        if obj.attachments is not None:
            to_update['attachments'] = [i.url for i in list(obj.attachments.values())]

        if obj.embeds is not None:
            to_update['embeds'] = [json.dumps(i.to_dict(), default=default_json) for i in obj.embeds]

        cls.update(**to_update).where(cls.id == obj.id).execute()

    @classmethod
    def from_disco_message(cls, obj):
        _, created = cls.get_or_create(
            id=obj.id,
            defaults=dict(
                channel_id=obj.channel_id,
                guild_id=(obj.guild_id if obj.guild_id else None),
                author=User.from_disco_user(obj.author),
                content=obj.with_proper_mentions,
                timestamp=obj.timestamp,
                edited_timestamp=obj.edited_timestamp,
                num_edits=(0 if not obj.edited_timestamp else 1),
                mentions=list(obj.mentions.keys()),
                emojis=list(map(int, EMOJI_RE.findall(obj.content))),
                attachments=[i.url for i in list(obj.attachments.values())],
                embeds=[json.dumps(i.to_dict(), default=default_json) for i in obj.embeds]))

        for user in list(obj.mentions.values()):
            User.from_disco_user(user)

        return created

    @classmethod
    def from_disco_message_many(cls, messages, safe=False):
        q = cls.insert_many(list(map(cls.convert_message, messages))).returning(cls.id)

        if safe:
            q = q.on_conflict_ignore()

        return q.execute()

    @staticmethod
    def convert_message(obj):
        return {
            'id': obj.id,
            'channel_id': obj.channel_id,
            'guild_id': (obj.guild_id if obj.guild_id else None),
            'author': User.from_disco_user(obj.author),
            'content': obj.with_proper_mentions,
            'timestamp': obj.timestamp,
            'edited_timestamp': obj.edited_timestamp,
            'num_edits': (0 if not obj.edited_timestamp else 1),
            'mentions': list(obj.mentions.keys()),
            'emojis': list(map(int, EMOJI_RE.findall(obj.content))),
            'attachments': [i.url for i in list(obj.attachments.values())],
            'embeds': [json.dumps(i.to_dict(), default=default_json) for i in obj.embeds],
        }

    @classmethod
    def for_channel(cls, channel):
        return cls.select().where(cls.channel_id == channel.id)

    @classmethod
    def create_message_link(cls):
        return 'https://discord.com/channels/{}/{}/{}'.format(
            cls.guild_id,
            cls.channel_id,
            cls.id
        )

@ModelBase.register
class Reaction(ModelBase):
    message_id = BigIntegerField()
    user_id = BigIntegerField()
    emoji_id = BigIntegerField(null=True)
    emoji_name = TextField()

    class Meta:
        table_name = 'reactions'

        indexes = (
            (('message_id', 'user_id', 'emoji_id', 'emoji_name'), True),
            (('user_id', ), False),
            (('emoji_name', 'emoji_id', ), False),
        )

    @classmethod
    def from_disco_reactors(cls, message_id, reaction, user_ids):
        cls.insert_many([
            {
                'message_id': message_id,
                'user_id': i,
                'emoji_id': reaction.emoji.id or None,
                'emoji_name': reaction.emoji.name or None
            } for i in user_ids
        ]).on_conflict_ignore().execute()

    @classmethod
    def from_disco_reaction(cls, obj):
        return cls.create(
            message_id=obj.message_id,
            user_id=obj.user_id,
            emoji_id=obj.emoji.id or None,
            emoji_name=obj.emoji.name or None)


@ModelBase.register
class MessageArchive(ModelBase):
    FORMATS = ['txt', 'csv', 'json']

    archive_id = UUIDField(primary_key=True, default=uuid.uuid4)

    message_ids = BinaryJSONField()

    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(default=lambda: datetime.utcnow() + timedelta(days=7))

    class Meta:
        table_name = 'message_archives'

        indexes = (
            (('created_at', ), False),
            (('expires_at', ), False)
        )

    @classmethod
    def create_from_message_ids(cls, message_ids):
        return cls.create(message_ids=message_ids)

    @property
    def url(self):
        return '{}/api/archive/{}.txt'.format(WEB_URL, self.archive_id)

    def encode(self, fmt='txt'):
        from rowboat.models.user import User

        if fmt not in self.FORMATS:
            raise Exception('Invalid format {}'.format(fmt))

        q = Message.select(
            Message.id,
            Message.channel_id,
            Message.timestamp,
            Message.content,
            Message.deleted,
            Message.attachments,
            User
        ).join(
            User
        ).where(
            (Message.id << self.message_ids)
        )

        if fmt == 'txt':
            return '\n'.join(map(self.encode_message_text, q))
        elif fmt == 'csv':
            return '\n'.join([
                'id,channel_id,timestamp,author_id,author,content,deleted,attachments'
            ] + list(map(self.encode_message_csv, q)))
        elif fmt == 'json':
            return json.dumps({
                'messages': list(map(self.encode_message_json, q))
            })

    @staticmethod
    def encode_message_text(msg):
        return '{m.timestamp} ({m.channel_id} / {m.id}) {m.author}: {m.content} ({attach})'.format(
            m=msg, attach=', '.join(map(str, msg.attachments or [])))

    @staticmethod
    def encode_message_csv(msg):
        def wrap(i):
            return '"{}"'.format(str(i).replace('"', '""'))

        return ','.join(map(wrap, [
            msg.id,
            msg.timestamp,
            msg.author.id,
            msg.author,
            msg.content,
            str(msg.deleted).lower(),
            ' '.join(msg.attachments or [])
        ]))

    @staticmethod
    def encode_message_json(msg):
        return dict(
            id=str(msg.id),
            timestamp=str(msg.timestamp),
            author_id=str(msg.author.id),
            username=msg.author.username,
            content=msg.content,
            deleted=msg.deleted,
            attachments=msg.attachments)


@ModelBase.register
class StarboardEntry(ModelBase):
    message = ForeignKeyField(Message, primary_key=True)

    # Information on where this starboard message lies
    star_channel_id = BigIntegerField(null=True)
    star_message_id = BigIntegerField(null=True)

    # List of user ids who stared this message, not guarenteed to be accurate
    stars = ArrayField(BigIntegerField, default=[])

    # List of user ids who starred this message, but are blocked
    blocked_stars = ArrayField(BigIntegerField, default=[])

    blocked = BooleanField(default=False)
    dirty = BooleanField(default=False)

    SQL = '''
        CREATE INDEX\
                IF NOT EXISTS starboard_entries_stars ON starboard_entries USING gin (stars);
    '''

    class Meta:
        table_name = 'starboard_entries'

        indexes = (
            (('star_channel_id', 'star_message_id'), True),
        )

    @classmethod
    def add_star(cls, message_id, user_id):
        sql = '''
            INSERT INTO starboard_entries (message_id, stars, blocked_stars, blocked, dirty)
            VALUES (%s, ARRAY[%s], ARRAY[]::integer[], false, true)
            ON CONFLICT (message_id)
            DO UPDATE
                SET stars = array_append(starboard_entries.stars, %s), dirty = true
                WHERE NOT starboard_entries.stars @> ARRAY[%s]
            '''
        cls.raw(sql, message_id, user_id, user_id, user_id).execute()

    @classmethod
    def remove_star(cls, message_id, user_id):
        sql = '''
            UPDATE starboard_entries
                SET
                    stars = array_remove(stars, %s),
                    blocked_stars = array_remove(stars, %s),
                    dirty = true
                WHERE message_id=%s AND starboard_entries.stars @> ARRAY[%s]
        '''
        cls.raw(sql, user_id, user_id, message_id, user_id).execute()

    @classmethod
    def block(cls, entity_id):
        sql = '''
            UPDATE starboard_entries
                SET stars = array_remove(stars, %s),
                    blocked_stars = array_append(blocked_stars, %s),
                WHERE starboard_entries.stars @> ARRAY[%s]
        '''
        cls.raw(sql, entity_id, entity_id, entity_id)

        StarboardEntry.update(
            blocked=True,
        ).where(
            (StarboardEntry.message.id << (
                StarboardEntry.select().join(Message).where(
                    (Message.author_id == entity_id)
                )
            ))
        ).execute()

    @classmethod
    def unblock(cls, entity_id):
        sql = '''
            UPDATE starboard_entries
                SET stars = array_append(stars, %s),
                    blocked_stars = array_remove(blocked_stars, %s),
                    dirty = true
                WHERE starboard_entries.stars @> ARRAY[%s]
        '''
        cls.raw(sql, entity_id, entity_id, entity_id)

        StarboardEntry.update(
            dirty=True,
            blocked=False,
        ).where(
            (StarboardEntry.message.id << (
                StarboardEntry.select().join(Message).where(
                    (Message.author_id == entity_id)
                )
            )) & (StarboardEntry.blocked == 1)
        ).execute()


@ModelBase.register
class Reminder(ModelBase):
    message_id = BigIntegerField(primary_key=True)

    created_at = DateTimeField(default=datetime.utcnow)
    remind_at = DateTimeField()
    content = TextField()

    class Meta:
        table_name = 'reminders'

    @classmethod
    def with_message_join(cls, fields=None):
        return cls.select(
            *(fields or (Reminder, Message))
        ).join(Message, on=(
            Reminder.message_id == Message.id
        ))

    @classmethod
    def count_for_user(cls, user_id):
        return cls.with_message_join().where(
            (Message.author_id == user_id)
        ).count()

    @classmethod
    def delete_for_user(cls, user_id):
        return cls.delete().where(
            (cls.message_id << cls.with_message_join((Message.id, )).where(
                (Message.author_id == user_id)
            ))
        ).execute()


@ModelBase.register
class Command(ModelBase):
    message_id = BigIntegerField(primary_key=True)

    plugin = TextField()
    command = TextField()
    version = TextField()
    success = BooleanField()
    traceback = TextField(null=True)

    class Meta:
        table_name = 'commands'

        indexes = (
            (('success', ), False),
            (('plugin', 'command'), False),
        )

    @classmethod
    def track(cls, event, command, exception=False):
        return cls.create(
            message_id=event.message.id,
            plugin=command.plugin.name,
            command=command.name,
            version=REV,
            success=not exception,
            traceback=traceback.format_exc() if exception else None,
        )
