import operator
import re
import string
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import reduce

import humanize
import pytz
from aenum import Enum, extend_enum
from disco.bot import CommandLevels
from disco.types.base import cached_property
from disco.util.emitter import Priority
from disco.util.sanitize import S
from disco.util.snowflake import to_datetime, to_unix

from rowboat.models.guild import Guild
from rowboat.plugins import CommandFail, CommandSuccess
from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.types import ChannelField, DictField, Field, ListField, SlottedModel, snowflake
from rowboat.types.plugin import PluginConfig
from rowboat.util import MetaException, ordered_load

from .pump import ModLogPump

# Dynamically updated by the plugin
Actions = Enum()

URL_REGEX = re.compile(r'(https?://[^\s]+)')


def filter_urls(content):
    return URL_REGEX.sub(r'<\1>', content)


class ChannelConfig(SlottedModel):
    compact = Field(bool, default=True)
    include = ListField(Actions)
    exclude = ListField(Actions)
    rich = ListField(Actions)

    timestamps = Field(bool, default=False)
    timezone = Field(str, default='US/Eastern')

    def validate(self):
        assert pytz.timezone(self.timezone) is not None

    @cached_property
    def tz(self):
        return pytz.timezone(self.timezone)

    @cached_property
    def subscribed(self):
        include = set(self.include if self.include else Actions.attrs)
        exclude = set(self.exclude if self.exclude else [])
        return include - exclude


class CustomFormat(SlottedModel):
    emoji = Field(str, default=None)
    format = Field(str, default=None)


class ModLogConfig(PluginConfig):
    resolved = Field(bool, default=False, private=True)

    ignored_users = ListField(snowflake)
    ignored_channels = ListField(snowflake)
    custom = DictField(str, CustomFormat)

    channels = DictField(ChannelField, ChannelConfig)
    new_member_threshold = Field(int, default=(15 * 60))

    _custom = DictField(dict, private=True)
    _channels = DictField(ChannelConfig, private=True)

    @cached_property
    def subscribed(self):
        return reduce(operator.or_, (i.subscribed for i in list(self.channels.values()))) if self.channels else set()


class Formatter(string.Formatter):
    def convert_field(self, value, conversion):
        if conversion in ('z', 's'):
            return S(str(value), escape_codeblocks=True)
        return str(value)


class Debounce(object):
    def __init__(self, plugin, guild_id, selector, events):
        self.plugin = plugin
        self.guild_id = guild_id
        self.selector = selector
        self.events = events
        self.timestamp = time.time()

    def is_expired(self):
        return time.time() - self.timestamp > 60

    def remove(self, event=None):
        self.plugin.debounces.remove(self, event)


class DebouncesCollection(object):
    def __init__(self):
        self._data = defaultdict(lambda: defaultdict(list))

    def __iter__(self):
        for top in list(self._data.values()):
            for bot in list(top.values()):
                for obj in bot:
                    yield obj

    def add(self, obj):
        for event_name in obj.events:
            self._data[obj.guild_id][event_name].append(obj)

    def remove(self, obj, event=None):
        for event_name in ([event] if event else obj.events):
            if event_name in obj.events:
                obj.events.remove(event_name)

            if obj in self._data[obj.guild_id][event_name]:
                self._data[obj.guild_id][event_name].remove(obj)

    def find(self, event, delete=True, **kwargs):
        guild_id = event.guild_id if hasattr(event, 'guild_id') else event.guild.id
        for obj in self._data[guild_id][event.__class__.__name__]:
            if obj.is_expired():
                obj.remove()
                continue

            for k, v in list(kwargs.items()):
                if obj.selector.get(k) != v:
                    continue

            if delete:
                obj.remove(event=event.__class__.__name__)
            return obj


@Plugin.with_config(ModLogConfig)
class ModLogPlugin(Plugin):
    fmt = Formatter()

    def load(self, ctx):
        if not Actions.attrs:
            self.action_simple = {}

            with open('data/actions_simple.yaml') as f:
                simple = ordered_load(f.read())

            for k, v in list(simple.items()):
                self.register_action(k, v)
        else:
            self.action_simple = ctx['action_simple']

        self.debounces = ctx.get('debounces') or DebouncesCollection()

        # Tracks modlogs that are silenced
        self.hushed = {}

        # Tracks pumps for all modlogs
        self.pumps = {}

        super(ModLogPlugin, self).load(ctx)

    def create_debounce(self, event, events, **kwargs):
        if isinstance(event, int):
            guild_id = event
        else:
            guild_id = event.guild_id if hasattr(event, 'guild_id') else event.guild.id
        bounce = Debounce(self, guild_id, kwargs, events)
        self.debounces.add(bounce)
        return bounce

    def unload(self, ctx):
        ctx['action_simple'] = self.action_simple
        ctx['debounces'] = self.debounces
        super(ModLogPlugin, self).unload(ctx)

    def resolve_channels(self, guild, config):
        self.log.info('Resolving channels for guild %s (%s)', guild.id, guild.name)

        channels = {}
        for key, channel in list(config.channels.items()):
            if isinstance(key, int):
                chan = guild.channels.select_one(id=key)
            else:
                chan = guild.channels.select_one(name=key)

            if not chan:
                raise MetaException('Failed to ModLog.resolve_channels', {
                    'guild_name': guild.name,
                    'guild_id': str(guild.id),
                    'key': str(key),
                    'config_channels': list(str(i) for i in list(config.channels.keys())),
                    'guild_channels': list(str(i) for i in list(guild.channels.keys())),
                })
            channels[chan.id] = channel

        self.log.info('Resolved channels for guild %s (%s): %s',
                      guild.id,
                      guild.name,
                      channels)

        if config._channels:
            self.log.warning('Overwriting previously resolved channels %s / %s', config._channels, channels)

        config._channels = channels

        config._custom = None
        if config.custom:
            rowboat_guild = self.call('CorePlugin.get_guild', guild.id)
            if rowboat_guild and rowboat_guild.is_whitelisted(Guild.WhitelistFlags.MODLOG_CUSTOM_FORMAT):
                custom = {}
                for action, override in list(config.custom.items()):
                    action = Actions.get(action)
                    if not action:
                        continue

                    custom[action] = override.to_dict()
                    if not custom[action].get('emoji'):
                        custom[action]['emoji'] = self.action_simple[action]['emoji']

                config._custom = custom

        config.resolved = True

    def register_action(self, name, simple):
        action = extend_enum(Actions, name, len(Actions) + 1)
        self.action_simple[action] = simple

    def log_action_ext(self, action, guild_id, **details):
        config = self.call('CorePlugin.get_config', guild_id)
        if not hasattr(config.plugins, 'modlog'):
            self.log.warning('log_action_ext ignored for %s, lack of modlog config', guild_id)
            return

        return self.log_action_raw(
            action,
            self.state.guilds.get(guild_id),
            getattr(config.plugins, 'modlog'),
            **details)

    def log_action(self, action, event, **details):
        details['e'] = event
        return self.log_action_raw(action, event.guild, event.config.get(), **details)

    def log_action_raw(self, action, guild, config, **details):
        if not config:
            return

        if not config.resolved:
            self.resolve_channels(guild, config)

        if not {action} & config.subscribed:
            return

        def generate_simple(chan_config):
            info = self.action_simple.get(action)

            if config._custom:
                if action in config._custom:
                    info = config._custom[action]

            # Format contents and create the message with the given emoji
            contents = self.fmt.format(str(info['format']), **details)
            msg = ':{}: {}'.format(info['emoji'], contents)

            if chan_config.timestamps:
                ts = datetime.now(chan_config.tz)
                msg = '`[{}]` '.format(ts.strftime('%H:%M:%S')) + msg

            if len(msg) > 2000:
                msg = msg[0:1997] + '...'

            return msg

        for channel_id, chan_config in list(config._channels.items()):
            if channel_id not in guild.channels:
                self.log.error('guild %s has outdated modlog channels (%s)', guild.id, channel_id)
                config._channels = list()
                config.resolved = False
                return

            if not {action} & chan_config.subscribed:
                continue

            msg = generate_simple(chan_config)

            if channel_id not in self.pumps:
                self.pumps[channel_id] = ModLogPump(
                    self.state.channels.get(channel_id),
                )
            self.pumps[channel_id].send(msg)

    @Plugin.command('hush', group='modlog', level=CommandLevels.ADMIN)
    def command_hush(self, event):
        if event.guild.id in self.hushed:
            raise CommandFail('Modlog is already hushed')

        self.hushed[event.guild.id] = True
        raise CommandSuccess('Modlog hushed, do your dirty work in peace')

    @Plugin.command('unhush', group='modlog', level=CommandLevels.ADMIN)
    def command_unhush(self, event):
        if event.guild.id not in self.hushed:
            raise CommandFail('Modlog is not hushed')

        del self.hushed[event.guild.id]
        raise CommandSuccess('Modlog unhushed, nobody saw anything')

    @Plugin.schedule(120)
    def cleanup_debounce(self):
        for obj in self.debounces:
            if obj.is_expired():
                obj.remove()

    @Plugin.listen('ChannelCreate')
    def on_channel_create(self, event):
        self.log_action(Actions.CHANNEL_CREATE, event)

    @Plugin.listen('ChannelDelete')
    def on_channel_delete(self, event):
        self.log_action(Actions.CHANNEL_DELETE, event)

    @Plugin.listen('GuildBanAdd')
    def on_guild_ban_add(self, event):
        debounce = self.debounces.find(event, user_id=event.user.id)
        if debounce:
            return

        self.log_action(Actions.GUILD_BAN_ADD, event)

    @Plugin.listen('GuildBanRemove')
    def on_guild_ban_remove(self, event):
        debounce = self.debounces.find(event, user_id=event.user.id)
        if debounce:
            return

        self.log_action(Actions.GUILD_BAN_REMOVE, event)

    @Plugin.listen('GuildMemberAdd')
    def on_guild_member_add(self, event):
        created = humanize.naturaltime(datetime.now(timezone.utc) - to_datetime(event.user.id))
        new = (
            event.config.new_member_threshold and
            (time.time() - to_unix(event.user.id)) < event.config.new_member_threshold
        )

        self.log_action(Actions.GUILD_MEMBER_ADD, event, new=' :new:' if new else '', created=created)

    @Plugin.listen('GuildMemberRemove')
    def on_guild_member_remove(self, event):
        debounce = self.debounces.find(event, user_id=event.user.id)

        if debounce:
            return

        self.log_action(Actions.GUILD_MEMBER_REMOVE, event)

    @Plugin.listen('GuildRoleCreate')
    def on_guild_role_create(self, event):
        self.log_action(Actions.GUILD_ROLE_CREATE, event)

    @Plugin.listen('GuildRoleDelete', priority=Priority.BEFORE)
    def on_guild_role_delete(self, event):
        pre_role = event.guild.roles.get(event.role_id)
        self.log_action(Actions.GUILD_ROLE_DELETE, event, pre_role=pre_role)

    @Plugin.listen('GuildMemberUpdate', priority=Priority.BEFORE)
    def on_guild_member_update(self, event):
        pre_member = event.guild.members.get(event.id)

        if not pre_member:
            return

        # Global debounce, used for large member updates
        debounce = self.debounces.find(event, user_id=event.user.id)
        if debounce:
            return

        # Log nickname changes
        if (pre_member.nick or event.nick) and pre_member.nick != event.nick:
            if not pre_member.nick:
                debounce = self.debounces.find(event, user_id=event.user.id, nickname=event.nick)
                if debounce:
                    return

                self.log_action(
                    Actions.ADD_NICK,
                    event,
                    nickname=event.nick)
            elif not event.nick:
                self.log_action(
                    Actions.RMV_NICK,
                    event,
                    nickname=pre_member.nick)
            else:
                self.log_action(
                    Actions.CHANGE_NICK,
                    event,
                    before=pre_member.nick or '<NO_NICK>',
                    after=event.nick or '<NO_NICK>')

        # Log role changes, which require diffing the pre/post roles on the member
        pre_roles = set(pre_member.roles)
        post_roles = set(event.roles)
        if pre_roles != post_roles:
            added = post_roles - pre_roles
            removed = pre_roles - post_roles

            # Log all instances of a role getting added
            for role in filter(bool, list(map(event.guild.roles.get, added))):
                debounce = self.debounces.find(
                    event,
                    user_id=event.user.id,
                    role_id=role.id,
                )
                if debounce:
                    continue

                self.log_action(Actions.GUILD_MEMBER_ROLES_ADD, event, role=role)

            for role in filter(bool, list(map(event.guild.roles.get, removed))):
                debounce = self.debounces.find(
                    event,
                    user_id=event.user.id,
                    role_id=role.id,
                )
                self.log_action(Actions.GUILD_MEMBER_ROLES_RMV, event, role=role)

    @Plugin.listen('PresenceUpdate', priority=Priority.BEFORE, metadata={'global_': True})
    def on_presence_update(self, event):
        plugin = self.bot.plugins.get('CorePlugin')
        if not plugin or not event.user:
            return

        subscribed_guilds = defaultdict(list)

        for guild_id, config in list(plugin.guilds.items()):
            guild = self.state.guilds.get(guild_id)
            if not guild:
                continue

            if event.user.id not in guild.members:
                continue

            config = config.get_config()
            if not config.plugins or not config.plugins.modlog:
                continue

            if event.user.id in config.plugins.modlog.ignored_users:
                continue

            if {Actions.CHANGE_USERNAME} & config.plugins.modlog.subscribed:
                subscribed_guilds[Actions.CHANGE_USERNAME].append((guild, config))

        if not len(subscribed_guilds):
            return

        pre_user = self.state.users.get(event.user.id)
        before = str(pre_user)

        if Actions.CHANGE_USERNAME in subscribed_guilds:
            if event.user.username is not None and event.user.username != pre_user.username:
                for guild, config in subscribed_guilds[Actions.CHANGE_USERNAME]:
                    self.log_action_raw(
                        Actions.CHANGE_USERNAME,
                        guild,
                        config.plugins.modlog,
                        before=before,
                        after=str(event.user),
                        e=event)

    @Plugin.listen('MessageUpdate', priority=Priority.BEFORE)
    def on_message_update(self, event):
        if event.author.id == self.state.me.id:
            return

        if event.author.id in event.config.ignored_users:
            return

        if event.channel_id in event.config.ignored_channels:
            return

        from rowboat.models.message import Message

        try:
            msg = Message.get(Message.id == event.id)
        except Message.DoesNotExist:
            return

        if not event.channel or not event.author:
            return

        if event.content is not None and msg.content != event.message.with_proper_mentions:
            self.log_action(
                Actions.MESSAGE_EDIT,
                event,
                before=filter_urls(msg.content),
                after=filter_urls(event.message.with_proper_mentions))

    @Plugin.listen('MessageDelete')
    def on_message_delete(self, event):
        if event.guild.id in self.hushed:
            return

        from rowboat.models.message import Message

        try:
            msg = Message.get(Message.id == event.id)
        except Message.DoesNotExist:
            return

        channel = self.state.channels.get(msg.channel_id)
        if not channel or not msg.author:
            return

        debounce = self.debounces.find(event, message_id=event.id)
        if debounce:
            return

        if msg.author.id == self.state.me.id:
            return

        if msg.author.id in event.config.ignored_users:
            return

        if msg.channel_id in event.config.ignored_channels:
            return

        # Truncate/limit the size of contents
        contents = filter_urls(msg.content)
        if len(contents) > 1750:
            contents = contents[:1750] + '... ({} more characters)'.format(
                len(contents) - 1750
            )

        self.log_action(Actions.MESSAGE_DELETE, event,
                        author=msg.author,
                        author_id=msg.author.id,
                        channel=channel,
                        msg=contents,
                        attachments='' if not msg.attachments else '({})'.format(
                            ', '.join('<{}>'.format(i) for i in msg.attachments)))

    @Plugin.listen('MessageDeleteBulk')
    def on_message_delete_bulk(self, event):
        channel = self.state.channels.get(event.channel_id)
        if not channel:
            return

        if event.guild.id in self.hushed:
            return

        from rowboat.models.message import MessageArchive
        archive = MessageArchive.create_from_message_ids(event.ids)
        self.log_action(Actions.MESSAGE_DELETE_BULK, event, log=archive.url, channel=channel, count=len(event.ids))

    #@Plugin.listen('VoiceStateUpdate', priority=Priority.SEQUENTIAL)
    @Plugin.listen("VoiceStateUpdate", priority=Priority.AFTER)
    def on_voice_state_update(self, event):
        old_vs = self.state.voice_states.get(event.session_id)

        # Moving channels
        if old_vs and event.channel_id:
            if old_vs.channel_id != event.channel_id:
                self.log_action(
                    Actions.VOICE_CHANNEL_MOVE,
                    event,
                    before_channel=old_vs.channel)
        elif old_vs:
            self.log_action(
                Actions.VOICE_CHANNEL_LEAVE,
                event,
                channel=old_vs.channel)

    #@Plugin.listen('IntegrationUpdate', priority=Priority.SEQUENTIAL)
    @Plugin.listen('IntegrationUpdate', priority=Priority.AFTER)
    def on_integration_update(self, event):
        self.log_action(Actions.INTEGRATION_UPDATE, event)
