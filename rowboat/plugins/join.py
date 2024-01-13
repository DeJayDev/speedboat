
import gevent
from disco.types.base import SlottedModel
from disco.types.guild import VerificationLevel

from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.types import Field, snowflake
from rowboat.types.plugin import PluginConfig


class JoinPluginConfigAdvanced(SlottedModel):
    low = Field(int, default=0)
    medium = Field(int, default=5)
    high = Field(int, default=10)
    highest = Field(int, default=30) # This is "VERY_HIGH" in Disco.


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
            return

        verification_level = event.guild.verification_level

        if not event.config.security:
            # Let's assume that if the server has join roles enabled and security disabled,
            # they don't care about email verification.
            try:
                event.member.add_role(event.config.join_role)
            except:
                print("Failed to add_role in join plugin for user {} in {}. join_role may be None? It is currently: {}".format(
                    event.member.id, event.guild.id, event.config.join_role))
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

        if verification_level is VerificationLevel.VERY_HIGH:
            gevent.spawn_later(event.config.advanced.highest, event.member.add_role, event.config.join_role)

