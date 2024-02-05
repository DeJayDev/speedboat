import time

from datadog import initialize, statsd
from disco.types.channel import ChannelType

from rowboat import ENV
from rowboat.plugins import RowboatPlugin as Plugin


def to_tags(obj):
    return ["{}:{}".format(k, v) for k, v in list(obj.items())]


class StatsPlugin(Plugin):
    global_plugin = True

    def load(self, ctx):
        super(StatsPlugin, self).load(ctx)
        if ENV == "docker":
            initialize(statsd_host="dd-agent", statsd_port=8125, hostname_from_config=False)
        else:
            initialize(statsd_host="127.0.0.1", statsd_port=8125, hostname_from_config=False)

        self.nonce = 0
        self.nonces = {}
        self.unhooked_send_message = self.client.api.channels_messages_create
        self.client.api.channels_messages_create = self.send_message_hook

    def unload(self, ctx):
        self.client.api.channels_messages_create = self.unhooked_send_message
        super(StatsPlugin, self).unload(ctx)

    def send_message_hook(self, *args, **kwargs):
        self.nonce += 1
        kwargs["nonce"] = self.nonce
        self.nonces[self.nonce] = time.time()
        return self.unhooked_send_message(*args, **kwargs)

    @Plugin.listen("")
    def on_gateway_event(self, event):
        metadata = {
            "event": event.__class__.__name__,
        }

        if hasattr(event, "guild_id"):
            metadata["guild_id"] = event.guild_id
        elif hasattr(event, "guild") and event.guild:
            metadata["guild_id"] = event.guild.id

        statsd.increment("gateway.events.received", tags=to_tags(metadata))

    @Plugin.schedule(180, init=False)
    def track_state(self):
        # Track members across all our guilds
        # for guild in self.state.guilds:
        #    statsd.gauge("guild.members", len(guild.members), tags=to_tags({
        #        "guild_id": guild.id
        #    }))

        # Track some state info
        statsd.gauge("disco.state.guilds", len(self.state.guilds))
        statsd.gauge("disco.state.channels", len(self.state.channels))
        statsd.gauge("disco.state.users", len(self.state.users))

    @Plugin.listen("MessageCreate")
    def on_message_create(self, event):
        if event.author.bot:
            return

        if event.channel.type == "DM":
            return

        tags = {
            "channel_id": event.channel_id,
            "author_id": event.author.id,
            "guild_id": event.guild.id
        }

        if event.author.id == self.client.state.me.id:
            if event.nonce in self.nonces:
                statsd.timing(
                    "latency.message_send",
                    time.time() - self.nonces[event.nonce],
                    tags=to_tags(tags)
                )
                del self.nonces[event.nonce]

        if event.message.mention_everyone:
            tags["mentions_everyone"] = "1"  # Does Datadog support booleans? It does now.

        statsd.increment("guild.messages.create", tags=to_tags(tags))

    @Plugin.listen("MessageUpdate")
    def on_message_update(self, event):
        if event.message.author.bot:
            return

        if event.channel.type == "DM":
            return

        tags = {
            "channel_id": event.channel_id,
            "author_id": event.author.id,
            "guild_id": event.guild.id
        }

        statsd.increment("guild.messages.update", tags=to_tags(tags))

    @Plugin.listen("MessageDelete")
    def on_message_delete(self, event):
        tags = {
            "channel_id": event.channel_id,
            "guild_id": event.guild_id,
        }

        statsd.increment("guild.messages.delete", tags=to_tags(tags))

    @Plugin.listen("MessageReactionAdd")
    def on_message_reaction_add(self, event):
        statsd.increment("guild.messages.reactions.add", tags=to_tags({
            "channel_id": event.channel_id,
            "user_id": event.user_id,
            "emoji_id": event.emoji.id,
            "emoji_name": event.emoji.name,
        }))

    @Plugin.listen("MessageReactionRemove")
    def on_message_reaction_remove(self, event):
        statsd.increment("guild.messages.reactions.remove", tags=to_tags({
            "channel_id": event.channel_id,
            "user_id": event.user_id,
            "emoji_id": event.emoji.id,
            "emoji_name": event.emoji.name,
        }))

    @Plugin.listen("GuildMemberAdd")
    def on_guild_member_add(self, event):
        if event.member.user.bot:
            return

        statsd.increment("guild.members.add", tags=to_tags({
            "guild_id": event.member.guild_id,  # this event fires a GuildMember, so we harvest the guild_id
        }))

    @Plugin.listen("GuildMemberRemove")
    def on_guild_member_remove(self, event):
        if event.user.bot:
            return

        statsd.increment("guild.members.remove", tags=to_tags({
            "guild_id": event.guild_id,  # this event fires the id as it's own variable.
        }))

    @Plugin.listen("GuildBanAdd")
    def on_guild_ban_add(self, event):
        statsd.increment("guild.bans.add")

    @Plugin.listen("GuildBanRemove")
    def on_guild_ban_remove(self, event):
        statsd.increment("guild.ban.remove")
