import arrow

from datetime import datetime
from holster.enum import Enum
from peewee import BigIntegerField, IntegerField, SmallIntegerField, TextField, BooleanField, DateTimeField
from playhouse.postgres_ext import BinaryJSONField

from rowboat.sql import ModelBase
from disco.api.http import APIException
from disco.types.guild import GuildMember

@ModelBase.register
class User(ModelBase):
    user_id = BigIntegerField(primary_key=True)
    username = TextField()
    discriminator = SmallIntegerField()
    avatar = TextField(null=True)
    bot = BooleanField()

    created_at = DateTimeField(default=datetime.utcnow)

    admin = BooleanField(default=False)

    SQL = '''
        CREATE INDEX IF NOT EXISTS users_username_trgm ON users USING gin(username gin_trgm_ops);
    '''

    class Meta:
        table_name = 'users'

        indexes = (
            (('user_id', 'username', 'discriminator'), True),
        )

    def serialize(self, us=False):
        base = {
            'id': str(self.user_id),
            'username': self.username,
            'discriminator': self.discriminator,
            'avatar': self.avatar,
            'bot': self.bot,
        }

        if us:
            base['admin'] = self.admin

        return base

    @property
    def id(self):
        return self.user_id

    @classmethod
    def ensure(cls, user, should_update=True):
        return cls.from_disco_user(user)

    @classmethod
    def with_id(cls, uid):
        try:
            return User.get(user_id=uid)
        except User.DoesNotExist:
            return

    @classmethod
    def from_disco_user(cls, user, should_update=True):
        # DEPRECATED
        obj, _ = cls.get_or_create(
            user_id=user.id,
            defaults={
                'username': user.username,
                'discriminator': user.discriminator,
                'avatar': user.avatar,
                'bot': user.bot
            })

        if should_update:
            updates = {}

            if obj.username != user.username:
                updates['username'] = user.username

            if obj.discriminator != user.discriminator:
                updates['discriminator'] = user.discriminator

            if obj.avatar != user.avatar:
                updates['avatar'] = user.avatar

            if updates:
                cls.update(**updates).where(User.user_id == user.id).execute()

        return obj

    def get_avatar_url(self, fmt='webp', size=1024):
        if not self.avatar:
            return None

        return 'https://cdn.discordapp.com/avatars/{}/{}.{}?size={}'.format(
            self.user_id,
            self.avatar,
            fmt,
            size
        )

    def __str__(self):
        return '{}#{}'.format(self.username, str(self.discriminator).zfill(4))

@ModelBase.register
class Infraction(ModelBase):
    Types = Enum(
        'MUTE',
        'KICK',
        'TEMPBAN',
        'SOFTBAN',
        'BAN',
        'TEMPMUTE',
        'UNBAN',
        'TEMPROLE',
        'WARNING',
        bitmask=False,
    )

    guild_id = BigIntegerField()
    user_id = BigIntegerField()
    actor_id = BigIntegerField(null=True)

    type_ = IntegerField(column_name='type')
    reason = TextField(null=True)
    metadata = BinaryJSONField(default={})

    expires_at = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.utcnow)
    active = BooleanField(default=True)
    messaged = BooleanField(default=False)

    class Meta:
        table_name = 'infractions'

        indexes = (
            (('guild_id', 'user_id'), False),
        )

    def serialize(self, guild=None, user=None, actor=None, include_metadata=False):
        base = {
            'id': str(self.id),
            'guild': (guild and guild.serialize()) or {'id': str(self.guild_id)},
            'user': (user and user.serialize()) or {'id': str(self.user_id)},
            'actor': (actor and actor.serialize()) or {'id': str(self.actor_id)},
            'reason': self.reason,
            'expires_at': self.expires_at,
            'created_at': self.created_at,
            'active': self.active,
            'messaged': self.messaged,
        }

        base['type'] = {
            'id': self.type_,
            'name': next(i.name for i in Infraction.Types.attrs if i.index == self.type_)
        }

        if include_metadata:
            base['metadata'] = self.metadata

        return base

    @staticmethod
    def infractions_config(event):
        return getattr(event.base_config.plugins, 'infractions', None)

    @classmethod
    def temprole(cls, plugin, event, member, role_id, reason, expires_at):
        User.from_disco_user(member.user)

        # TODO: modlog
        # RE Above: yeah holy fuck the modlog plugin sucks, i understand its for queueing but shit
        # I'll do it later.

        try:
            member.add_role(role_id, reason=reason)
        except APIException as err:
            if err.status_code == 50013:
                plugin.call(
                    'ModLogPlugin.log_action_ext',
                    Actions.PERMISSION_ERROR,
                    event.guild.id,
                    permission='add roles',
                )
                event.channel.send_message('I do not have permission to role this member. Action cancelled.')
                return

        cls.create(
            guild_id=event.guild.id,
            user_id=member.user.id,
            actor_id=event.author.id,
            type_=cls.Types.TEMPROLE,
            reason=reason,
            expires_at=expires_at,
            metadata={'role': role_id})

    @classmethod
    def kick(cls, plugin, event, member, reason):
        from rowboat.plugins.modlog import Actions

        # Prevent the GuildMemberRemove log event from triggering
        plugin.call(
            'ModLogPlugin.create_debounce',
            event,
            ['GuildMemberRemove'],
            user_id=member.user.id
        )

        msg_status = cls.send_message('kicked', member.user, event.guild, reason)

        try:
            member.kick(reason=reason)
        except APIException as err:
            if err.status_code == 50013:
                plugin.call(
                    'ModLogPlugin.log_action_ext',
                    Actions.PERMISSION_ERROR,
                    event.guild.id,
                    permission='kick users',
                )
                event.channel.send_message('I do not have permission to kick. Action cancelled.')
                return

        # Create a kick modlog event
        plugin.call(
            'ModLogPlugin.log_action_ext',
            Actions.MEMBER_KICK,
            event.guild.id,
            member=member,
            actor=str(event.author) if event.author.id != member.id else 'Automatic',
            reason=reason or 'no reason'
        )

        cls.create(
            guild_id=member.guild_id,
            user_id=member.user.id,
            actor_id=event.author.id,
            type_=cls.Types.KICK,
            reason=reason,
            messaged=msg_status)

    @classmethod
    def tempban(cls, plugin, event, member, reason, expires_at):
        from rowboat.plugins.modlog import Actions
        User.from_disco_user(member.user)

        plugin.call(
            'ModLogPlugin.create_debounce',
            event,
            ['GuildMemberRemove', 'GuildBanAdd'],
            user_id=member.user.id
        )

        msg_status = cls.send_message('banned', member.user, event.guild, reason, expires_at)

        member.ban(reason=reason)

        plugin.call(
            'ModLogPlugin.log_action_ext',
            Actions.MEMBER_TEMPBAN,
            event.guild.id,
            member=member,
            actor=str(event.author) if event.author.id != member.id else 'Automatic',
            reason=reason or 'no reason',
            expires=expires_at,
        )

        cls.create(
            guild_id=member.guild_id,
            user_id=member.user.id,
            actor_id=event.author.id,
            type_=cls.Types.TEMPBAN,
            reason=reason,
            expires_at=expires_at,
            messaged=msg_status)

    @classmethod
    def softban(cls, plugin, event, member, reason):
        from rowboat.plugins.modlog import Actions
        User.from_disco_user(member.user)

        plugin.call(
            'ModLogPlugin.create_debounce',
            event,
            ['GuildMemberRemove', 'GuildBanAdd', 'GuildBanRemove'],
            user_id=member.user.id
        )

        msg_status = cls.send_message('softbanned', member.user, event.guild, reason)

        member.ban(delete_message_days=7, reason=reason)
        member.unban(reason=reason)

        plugin.call(
            'ModLogPlugin.log_action_ext',
            Actions.MEMBER_SOFTBAN,
            event.guild.id,
            member=member,
            actor=str(event.author) if event.author.id != member.id else 'Automatic',
            reason=reason or 'no reason'
        )

        cls.create(
            guild_id=member.guild_id,
            user_id=member.user.id,
            actor_id=event.author.id,
            type_=cls.Types.SOFTBAN,
            reason=reason)

    @classmethod
    def ban(cls, plugin, event, member, reason, guild):
        from rowboat.plugins.modlog import Actions
        if isinstance(member, int):
            user_id = member
        else:
            user_id = member.user.id

        plugin.call(
            'ModLogPlugin.create_debounce',
            event,
            ['GuildMemberRemove', 'GuildBanAdd'],
            user_id=user_id,
        )

        msg_status = cls.send_message('banned', member, event.guild, reason)

        guild.create_ban(user_id, reason=reason)

        plugin.call(
            'ModLogPlugin.log_action_ext',
            Actions.MEMBER_BAN,
            event.guild.id,
            user=str(member),
            user_id=user_id,
            actor=str(event.author) if event.author.id != user_id else 'Automatic',
            reason=reason or 'no reason'
        )

        cls.create(
            guild_id=guild.id,
            user_id=user_id,
            actor_id=event.author.id,
            type_=cls.Types.BAN,
            reason=reason,
            messaged=msg_status)

    @classmethod
    def warn(cls, plugin, event, member, reason, guild):
        from rowboat.plugins.modlog import Actions
        User.from_disco_user(member.user)
        user_id = member.user.id

        msg_status = cls.send_message('warned', member.user, event.guild, reason)

        plugin.call(
            'ModLogPlugin.log_action_ext',
            Actions.MEMBER_WARNED,
            event.guild.id,
            member=member,
            actor=str(event.author) if event.author.id != member.id else 'Automatic',
            reason=reason or 'no reason'
        )

        cls.create(
            guild_id=guild.id,
            user_id=user_id,
            actor_id=event.author.id,
            type_=cls.Types.WARNING,
            reason=reason,
            messaged=msg_status)

    @classmethod
    def mute(cls, plugin, event, member, reason):
        from rowboat.plugins.modlog import Actions
        infractions_config = cls.infractions_config(event)

        plugin.call(
            'ModLogPlugin.create_debounce',
            event,
            ['GuildMemberUpdate'],
            user_id=member.user.id,
            role_id=infractions_config.mute_role,
        )

        member.add_role(infractions_config.mute_role, reason=reason)

        msg_status = cls.send_message('muted', member.user, event.guild, reason)
        
        plugin.call(
            'ModLogPlugin.log_action_ext',
            Actions.MEMBER_MUTED,
            event.guild.id,
            member=member,
            actor=str(event.author) if event.author.id != member.id else 'Automatic',
            reason=reason or 'no reason'
        )

        cls.create(
            guild_id=event.guild.id,
            user_id=member.user.id,
            actor_id=event.author.id,
            type_=cls.Types.MUTE,
            reason=reason,
            metadata={'role': infractions_config.mute_role},
            messaged=msg_status)

    @classmethod
    def tempmute(cls, plugin, event, member, reason, expires_at):
        from rowboat.plugins.modlog import Actions
        infractions_config = cls.infractions_config(event)

        if not infractions_config.mute_role:
            plugin.log.warning('Cannot tempmute member %s, no tempmute role', member.id)
            return

        plugin.call(
            'ModLogPlugin.create_debounce',
            event,
            ['GuildMemberUpdate'],
            user_id=member.user.id,
            role_id=infractions_config.mute_role,
        )

        member.add_role(infractions_config.mute_role, reason=reason)

        msg_status = cls.send_message('muted', member.user, event.guild, reason, expires_atM)

        plugin.call(
            'ModLogPlugin.log_action_ext',
            Actions.MEMBER_TEMP_MUTED,
            event.guild.id,
            member=member,
            actor=str(event.author) if event.author.id != member.id else 'Automatic',
            reason=reason or 'no reason',
            expires=expires_at,
        )

        cls.create(
            guild_id=event.guild.id,
            user_id=member.user.id,
            actor_id=event.author.id,
            type_=cls.Types.TEMPMUTE,
            reason=reason,
            expires_at=expires_at,
            metadata={'role': infractions_config.mute_role},
            messaged=msg_status)

    @classmethod
    def send_message(cls, action, user, guild, reason=None, expires_at=None):
        msg_status = False
        do_not_message = False

        if isinstance(user, int):
            if guild.get_member(user):
                user = guild.get_member(user).user # got em
            else:
                do_not_message = True

        if isinstance(user, GuildMember):
            if user.user.bot:
                do_not_message = True
            else:
                user = user.user # 👌

        if isinstance(user, User):
            do_not_message = user.bot

        if do_not_message:
            return msg_status
                
        emojis = {
            'warned': 'warning',
            'muted': 'speak_no_evil',
            'kicked': 'boot',
            'softbanned': 'hammer',
            'banned': 'hammer'
        }
        
        expires = ''

        if expires_at:
            expires = '\n\n:timer: This action will expire in {}'.format(
                arrow.get(expires_at - datetime.utcnow()).humanize())
        
        try:
            user.open_dm().send_message(':{}: You were **{}** from {} {} {}'.format(
                emojis[action] if action in emojis else 'exclaimation',
                action,
                guild.name,
                ('for: ' + reason) if reason else '',
                expires, # This doesn't have an ugly if statement because if it's not defined it's None.
            ))
                            
            msg_status = True
        except APIException as err:
            msg_status = False # Multiple bad things can happen here, so we'll just... do this.
            #print('Could not DM member {}'.format(user)

        return msg_status

    @classmethod
    def clear_active(cls, event, user_id, types):
        """
        Marks a previously active tempmute as inactive for the given event/user.
        This should be used in all locations where we either think this is no
        longer active (e.g. the mute role was removed) _or_ when we don't want to
        unmute the user any longer, e.g. they've been remuted by another command.
        """
        return cls.update(active=False).where(
            (cls.guild_id == event.guild.id) &
            (cls.user_id == user_id) &
            (cls.type_ << types) &
            (cls.active == 1)
        ).execute() >= 1

@ModelBase.register
class StarboardBlock(ModelBase):
    guild_id = BigIntegerField()
    user_id = BigIntegerField()
    actor_id = BigIntegerField()

    class Meta:
        indexes = (
            (('guild_id', 'user_id'), True),
        )

@ModelBase.register
class XPBlock(ModelBase):
    guild_id = BigIntegerField()
    user_id = BigIntegerField()
    actor_id = BigIntegerField()

    class Meta:
        indexes = (
            (('guild_id', 'user_id'), True),
        )
