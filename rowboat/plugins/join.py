from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.types import Field, snowflake
from rowboat.types.plugin import PluginConfig

class JoinPluginConfig(PluginConfig):
    join_role = Field(snowflake, default=None)
    pass


@Plugin.with_config(JoinPluginConfig)
class JoinPlugin(Plugin):

    @Plugin.listen('GuildMemberAdd')
    def on_guild_member_add(self, event):
        if event.member.user.bot: 
            return # I simply do not care

        event.member.add_role(event.config.join_role)
  