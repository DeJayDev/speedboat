import json
import re
import urllib.parse
from urllib.parse import unquote

from disco.types.base import cached_property
from disco.types.channel import ChannelType
from disco.util.sanitize import S

from rowboat.constants import INVITE_LINK_RE, URL_RE
from rowboat.models.message import Message
from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.plugins.modlog import Actions
from rowboat.redis import rdb
from rowboat.types import ChannelField, DictField, Field, ListField, SlottedModel, lower, snowflake
from rowboat.types.plugin import PluginConfig
from rowboat.util.stats import timed
from rowboat.util.zalgo import ZALGO_RE


class CensorReason:
    INVITE = 0
    DOMAIN = 1
    WORD = 2
    ZALGO = 3


class CensorSubConfig(SlottedModel):
    filter_zalgo = Field(bool, default=True)

    filter_invites = Field(bool, default=True)
    invite_filter_ignored_channels = ListField(lower, default=[])
    invites_guild_whitelist = ListField(snowflake, default=[])
    invites_whitelist = ListField(lower, default=[])
    invites_blacklist = ListField(lower, default=[])

    filter_domains = Field(bool, default=True)
    domain_filter_ignored_channels = ListField(lower, default=[])
    domains_whitelist = ListField(lower, default=[])
    domains_blacklist = ListField(lower, default=[])

    blocked_words = ListField(lower, default=[])
    blocked_tokens = ListField(lower, default=[])

    @cached_property
    def blocked_re(self):
        return re.compile('({})'.format('|'.join(
            list(map(re.escape, self.blocked_tokens)) +
            ['\\b{}\\b'.format(re.escape(k)) for k in self.blocked_words]
        )), re.I)


class CensorConfig(PluginConfig):
    levels = DictField(int, CensorSubConfig)
    channels = DictField(ChannelField, CensorSubConfig)


# It's bad kids!
class Censorship(Exception):
    def __init__(self, reason, event, ctx):
        self.reason = reason
        self.event = event
        self.ctx = ctx
        self.content = S(event.content, escape_codeblocks=True)

    @property
    def details(self):
        if self.reason is CensorReason.INVITE:
            if self.ctx['guild']:
                return 'invite `{}` to {}'.format(
                    self.ctx['invite'],
                    S(self.ctx['guild']['name'], escape_codeblocks=True)
                )
            else:
                return 'invite `{}`'.format(self.ctx['invite'])
        elif self.reason is CensorReason.DOMAIN:
            if self.ctx['hit'] == 'whitelist':
                return 'domain `{}` is not in whitelist'.format(S(self.ctx['domain'], escape_codeblocks=True))
            elif self.ctx['hit'] == 'blacklist':
                return 'domain `{}` is in blacklist'.format(S(self.ctx['domain'], escape_codeblocks=True))
            else:
                return 'because links are not allowed here'
        elif self.reason is CensorReason.WORD:
            return 'found blacklisted words `{}`'.format(
                ', '.join([S(i, escape_codeblocks=True) for i in self.ctx['words']]))
        elif self.reason is CensorReason.ZALGO:
            return 'found zalgo at position `{}` in text'.format(
                self.ctx['position']
            )
        else:
            return '...unsure why this message was censored. Please notify my developer.'


@Plugin.with_config(CensorConfig)
class CensorPlugin(Plugin):
    def compute_relevant_configs(self, event, author):
        if event.channel_id in event.config.channels:
            yield event.config.channels[event.channel.id]

        if event.config.levels:
            user_level = int(self.bot.plugins.get('CorePlugin').get_level(event.guild, author))

            for level, config in list(event.config.levels.items()):
                if user_level <= level:
                    yield config

    def get_invite_info(self, code):
        if rdb.exists('inv:{}'.format(code)):
            return json.loads(rdb.get('inv:{}'.format(code)))

        try:
            obj = self.client.api.invites_get(code)
        except:
            return

        obj = {
            'id': obj.guild.id,
            'name': obj.guild.name,
            'icon': obj.guild.icon
        }

        # Cache for 12 hours
        rdb.setex('inv:{}'.format(code), 43200, json.dumps(obj))
        return obj

    @Plugin.listen('MessageUpdate')
    def on_message_update(self, event):
        if event.message.author.bot or not event.content:
            return

        try:
            msg = Message.get(id=event.id)
        except Message.DoesNotExist:
            self.log.warning('Not censoring MessageUpdate for id %s, %s, no stored message', event.channel_id, event.id)
            return

        return self.on_message_create(
            event,
            author=event.guild.get_member(msg.author_id))

    @Plugin.listen('MessageCreate')
    def on_message_create(self, event, author=None):
        author = author or event.author

        if author.id == self.state.me.id:
            return

        if event.message.author.bot or event.channel.type is ChannelType.DM:
            return

        if event.webhook_id:
            return

        configs = list(self.compute_relevant_configs(event, author))
        if not configs:
            return

        tags = {'guild_id': event.guild.id, 'channel_id': event.channel.id}
        with timed('rowboat.plugin.censor.duration', tags=tags):
            try:
                for config in configs:
                    if config.filter_zalgo:
                        self.filter_zalgo(event, config)

                    if config.filter_invites:
                        self.filter_invites(event, config)

                    if config.filter_domains:
                        if str(event.channel.id) not in config.domain_filter_ignored_channels:
                            self.filter_domains(event, config)

                    if config.blocked_words or config.blocked_tokens:
                        self.filter_blocked_words(event, config)
            except Censorship as c:
                self.call(
                    'ModLogPlugin.create_debounce',
                    event,
                    ['MessageDelete'],
                    message_id=event.message.id,
                )

                try:
                    event.delete()

                    self.call(
                        'ModLogPlugin.log_action_ext',
                        Actions.CENSORED,
                        event.guild.id,
                        e=event,
                        c=c)
                except:
                    self.log.exception('Failed to delete censored message: ')

    def filter_zalgo(self, event, config):
        s = ZALGO_RE.search(event.content)
        if s:
            raise Censorship(CensorReason.ZALGO, event, ctx={
                'position': s.start()
            })

    def filter_invites(self, event, config):
        invites = INVITE_LINK_RE.findall(unquote(event.content))

        for _, invite in invites:
            invite_info = self.get_invite_info(invite)

            need_whitelist = (
                    config.invites_guild_whitelist or
                    (config.invites_whitelist or not config.invites_blacklist)
            )
            whitelisted = False

            if invite_info and invite_info.get('id') in config.invites_guild_whitelist:
                whitelisted = True

            if invite.lower() in config.invites_whitelist:
                whitelisted = True

            if need_whitelist and not whitelisted:
                raise Censorship(CensorReason.INVITE, event, ctx={
                    'hit': 'whitelist',
                    'invite': invite,
                    'guild': invite_info,
                })
            elif config.invites_blacklist and invite.lower() in config.invites_blacklist:
                raise Censorship(CensorReason.INVITE, event, ctx={
                    'hit': 'blacklist',
                    'invite': invite,
                    'guild': invite_info,
                })

    def filter_domains(self, event, config):
        urls = URL_RE.findall(URL_RE.sub('', event.content))

        for url in urls:
            try:
                parsed = urllib.parse.urlparse(url)
            except:
                continue

            if config.domains_whitelist and parsed.netloc.lower() not in config.domains_whitelist:
                raise Censorship(CensorReason.DOMAIN, event, ctx={
                    'hit': 'whitelist',
                    'url': url,
                    'domain': parsed.netloc,
                })
            elif config.domains_blacklist and parsed.netloc.lower() in config.domains_blacklist:
                raise Censorship(CensorReason.DOMAIN, event, ctx={
                    'hit': 'blacklist',
                    'url': url,
                    'domain': parsed.netloc
                })
            else:
                raise Censorship(CensorReason.DOMAIN, event, ctx={
                    'hit': 'other',
                    'url': url,
                    'domain': parsed.netloc
                })

    def filter_blocked_words(self, event, config):
        blocked_words = config.blocked_re.findall(event.content)

        if blocked_words:
            raise Censorship(CensorReason.WORD, event, ctx={
                'words': blocked_words,
            })
