from datetime import datetime, timedelta

import gevent
from disco.types.base import SlottedModel
from disco.types.guild import VerificationLevel
from disco.util.snowflake import to_datetime

from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.types import Field, snowflake
from rowboat.types.plugin import PluginConfig


class JoinPluginConfigAdvanced(SlottedModel):
    low = Field(int, default=0)
    medium = Field(int, default=5)
    high = Field(int, default=10)
    highest = Field(int, default=30, alias='extreme')  # Disco calls it extreme, the client calls it Highest.


class JoinPluginConfig(PluginConfig):
    join_role = Field(snowflake, default=None)
    security = Field(bool, default=False)
    advanced = Field(JoinPluginConfigAdvanced)
    pass


@Plugin.with_config(JoinPluginConfig)
class JoinPlugin(Plugin):

    @Plugin.listen('GuildMemberAdd')
    def on_guild_member_add(self, event):
        if event.member.user.bot:
            return  # I simply do not care

        verification_level = event.guild.verification_level

        if not event.config.security:
            # Let's assume that if the server has join roles enabled and security disabled,
            # they don't care about email verification.
            event.member.add_role(event.config.join_role)
            return

        if verification_level is VerificationLevel.LOW:  # "Must have a verified email on their Discord account"
            # We take a "guess" that if the server has join roles enabled, they don't care about email verification.
            event.member.add_role(event.config.join_role)
            gevent.spawn_later(event.config.advanced.low, event.member.add_role, event.config.join_role)
            return

        if verification_level is VerificationLevel.MEDIUM:
            gevent.spawn_later(event.config.advanced.medium, event.member.add_role, event.config.join_role)

        if verification_level is VerificationLevel.HIGH:
            gevent.spawn_later(event.config.advanced.high, event.member.add_role, event.config.join_role)

        if verification_level is VerificationLevel.EXTREME:
            gevent.spawn_later(event.config.advanced.highest, event.member.add_role, event.config.join_role)

    @Plugin.command('debugdelay', '[length:int]', group='join', level=-1)
    def trigger_delay(self, event, length: int = None):
        length = length if length else 10

        msg = event.channel.send_message("Sending later...")

        def calc_timediff():
            return "Scheduled for {} after trigger, took {}".format(length, (datetime.now() - to_datetime(msg.id)))

        gevent.spawn_later(length,
                           lambda: event.channel.send_message("Scheduled for {} after trigger, took {}"
                                                              .format(length, (datetime.now() - to_datetime(msg.id)) / timedelta(seconds=1))))
