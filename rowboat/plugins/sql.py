import time
from datetime import datetime

import cairosvg
import gevent
import markovify
import psycopg2
import pygal
from disco.types.channel import Channel as DiscoChannel
from disco.types.channel import ChannelType, MessageIterator
from disco.types.guild import Guild as DiscoGuild
from disco.types.message import MessageTable
from disco.types.permissions import Permissions
from disco.types.user import User as DiscoUser
from disco.util.emitter import Priority
from disco.util.snowflake import from_datetime, to_datetime
from gevent.pool import Pool

from rowboat.models.channel import Channel
from rowboat.models.guild import GuildEmoji, GuildVoiceSession
from rowboat.models.message import Message, Reaction
from rowboat.models.user import User
from rowboat.plugins import CommandFail, CommandSuccess
from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.sql import database
from rowboat.tasks.backfill import backfill_channel, backfill_guild
from rowboat.util.input import parse_duration
from rowboat.util.reqaddons import DiscordStyle


class SQLPlugin(Plugin):
    global_plugin = True

    def load(self, ctx):
        self.models = ctx.get("models", {})
        self.backfills = {}
        super(SQLPlugin, self).load(ctx)

    def unload(self, ctx):
        ctx["models"] = self.models
        super(SQLPlugin, self).unload(ctx)

    #@Plugin.listen("VoiceStateUpdate", priority=Priority.SEQUENTIAL)
    @Plugin.listen("VoiceStateUpdate", priority=Priority.AFTER)
    def on_voice_state_update(self, event):
        pre_state = self.state.voice_states.get(event.session_id)
        guild = self.state.guilds[event.guild_id]
        if guild.afk_channel_id is not event.channel_id:
            GuildVoiceSession.create_or_update(pre_state, event.state)

    @Plugin.listen("GuildMemberUpdate")
    def on_presence_update(self, event):
        updates = {}

        if event.user.avatar is not None:
            updates["avatar"] = event.user.avatar

        if event.user.username is not None:
            updates["username"] = event.user.username

        if event.user.bot:
            return

        if not updates:
            return

        User.update(**updates).where((User.user_id == event.user.id)).execute()

    @Plugin.listen("MessageCreate")
    def on_message_create(self, event):
        if event.message.author.bot:
            return
        Message.from_disco_message(event.message)

    @Plugin.listen("MessageUpdate")
    def on_message_update(self, event):
        Message.from_disco_message_update(event.message)

    @Plugin.listen("MessageDelete")
    def on_message_delete(self, event):
        Message.update(deleted=True).where(Message.id == event.id).execute()

    @Plugin.listen("MessageDeleteBulk")
    def on_message_delete_bulk(self, event):
        Message.update(deleted=True).where((Message.id << event.ids)).execute()

    @Plugin.listen("MessageReactionAdd", priority=Priority.BEFORE)
    def on_message_reaction_add(self, event):
        Reaction.from_disco_reaction(event)

    @Plugin.listen("MessageReactionRemove", priority=Priority.BEFORE)
    def on_message_reaction_remove(self, event):
        Reaction.delete().where(
            (Reaction.message_id == event.message_id) &
            (Reaction.user_id == event.user_id) &
            (Reaction.emoji_id == (event.emoji.id or None)) &
            (Reaction.emoji_name == (event.emoji.name or None))).execute()

    @Plugin.listen("MessageReactionRemoveAll")
    def on_message_reaction_remove_all(self, event):
        Reaction.delete().where((Reaction.message_id == event.message_id)).execute()

    @Plugin.listen("GuildEmojisUpdate", priority=Priority.BEFORE)
    def on_guild_emojis_update(self, event):
        ids = list()

        for emoji in event.emojis:
            GuildEmoji.from_disco_guild_emoji(emoji)
            ids.append(emoji.id)

        GuildEmoji.update(deleted=True).where(
            (GuildEmoji.guild_id == event.guild_id) &
            (~(GuildEmoji.emoji_id << ids))
        ).execute()

    # @Plugin.listen("GuildCreate")
    # def on_guild_create(self, event):
    #     for channel in list(event.channels.values()):
    #         Channel.from_disco_channel(channel)

    #     for emoji in list(event.emojis.values()):
    #         GuildEmoji.from_disco_guild_emoji(emoji)

    @Plugin.listen("GuildDelete")
    def on_guild_delete(self, event):
        if event.deleted:
            Channel.update(deleted=True).where(
                Channel.guild_id == event.id
            ).execute()

    @Plugin.listen("ChannelCreate")
    def on_channel_create(self, event):
        Channel.from_disco_channel(event.channel)

    @Plugin.listen("ChannelUpdate")
    def on_channel_update(self, event):
        Channel.from_disco_channel(event.channel)

    @Plugin.listen("ChannelDelete")
    def on_channel_delete(self, event):
        Channel.update(deleted=True).where(Channel.channel_id == event.channel.id).execute()

    @Plugin.command("sql", level=-1, global_=True)
    def command_sql(self, event):
        conn = database.obj.connection()

        try:
            tbl = MessageTable(codeblock=False)

            with conn.cursor() as cur:
                start = time.time()
                cur.execute(event.codeblock.format(e=event))
                dur = time.time() - start
                if not cur.description:
                    raise CommandSuccess("execution complete (had no return)")
                else:
                    tbl.set_header(*[desc[0] for desc in cur.description])

                    for row in cur.fetchall():
                        tbl.add(*row)

                    result = tbl.compile()
                    if len(result) > 1900:
                        return event.msg.reply(
                            "_took {}ms_".format(int(dur * 1000)),
                            attachments=[("result.txt", result)])

                    event.msg.reply("```" + result + "```\n_took {}ms_\n".format(int(dur * 1000)))
        except psycopg2.Error as e:
            event.msg.reply("```{}```".format(e.pgerror))

    @Plugin.command("init", "<entity:user|channel>", level=-1, group="markov", global_=True)
    def command_markov(self, event, entity):
        if isinstance(entity, DiscoUser):
            q = Message.select().where(Message.author_id == entity.id).limit(500000)
        else:
            q = Message.select().where(Message.channel_id == entity.id).limit(500000)

        text = [msg.content for msg in q]
        self.models[entity.id] = markovify.NewlineText("\n".join(text))
        raise CommandSuccess("Created markov model for {} using {} messages".format(entity, len(text)))

    @Plugin.command("one", "<entity:user|channel>", level=-1, group="markov", global_=True)
    def command_markov_one(self, event, entity):
        if entity.id not in self.models:
            raise CommandFail("No model created yet for {}".format(entity))

        sentence = self.models[entity.id].make_sentence(max_overlap_ratio=1, max_overlap_total=500)
        if not sentence:
            raise CommandFail("Not enough data :(")

        event.msg.reply("{}: {}".format(entity, sentence))

    @Plugin.command("many", "<entity:user|channel> [count|int]", level=-1, group="markov", global_=True)
    def command_markov_many(self, event, entity, count=5):
        if entity.id not in self.models:
            raise CommandFail("No model created yet for {}".format(entity))

        for _ in range(int(count)):
            sentence = self.models[entity.id].make_sentence(max_overlap_total=500)
            if not sentence:
                raise CommandFail("Not enough data :(")
            event.msg.reply("{}: {}".format(entity, sentence))

    @Plugin.command("list", level=-1, group="markov", global_=True)
    def command_markov_list(self, event):
        event.msg.reply("`{}`".format(", ".join(map(str, list(self.models.keys())))))

    @Plugin.command("delete", "<oid:snowflake>", level=-1, group="markov", global_=True)
    def command_markov_delete(self, event, oid):
        if oid not in self.models:
            return event.msg.reply(":warning: no model with that ID")

        del self.models[oid]
        raise CommandSuccess("Deleted model")

    @Plugin.command("clear", level=-1, group="markov", global_=True)
    def command_markov_clear(self, event):
        self.models = {}
        raise CommandSuccess("Cleared all models")

    @Plugin.command("message", "<channel:snowflake> <message:snowflake>", level=-1, group="backfill", global_=True)
    def command_backfill_message(self, event, channel, message):
        channel = self.state.channels.get(channel)
        Message.from_disco_message(channel.get_message(message))
        raise CommandSuccess("Backfill Complete")

    @Plugin.command("reactions", "<message:snowflake>", level=-1, group="backfill", global_=True)
    def command_sql_reactions(self, event, message):
        try:
            message = Message.get(id=message)
        except Message.DoesNotExist:
            raise CommandFail("No message found")

        message = self.state.channels.get(message.channel_id).get_message(message.id)
        for reaction in message.reactions:
            for users in message.get_reactors(reaction.emoji, bulk=True):
                Reaction.from_disco_reactors(message.id, reaction, (i.id for i in users))

    @Plugin.command("global", "<duration:str> [pool:int]", level=-1, global_=True, context={"mode": "global"}, group="recover")
    @Plugin.command("here", "<duration:str> [pool:int]", level=-1, global_=True, context={"mode": "here"}, group="recover")
    def command_recover(self, event, duration, pool=4, mode=None):
        channels = list()
        if mode == "global":
            chlist = list(self.state.channels.values())
        else:
            chlist = list(event.guild.channels.values())
        for gch in chlist:
            if self.state.channels[gch.id].type is ChannelType.GUILD_TEXT:
                if self.state.channels[gch.id].get_permissions(self.state.me.id).can(Permissions.VIEW_CHANNEL, Permissions.READ_MESSAGE_HISTORY):
                    channels.append(self.state.channels[gch.id])

        start_at = parse_duration(duration, negative=True)
        pool = Pool(pool)

        total = len(channels)
        msg = event.msg.reply("Recovery Status: 0/{}".format(total))
        recoveries = list()

        def updater():
            last = len(recoveries)

            while True:
                if last != len(recoveries):
                    last = len(recoveries)
                    msg.edit("Recovery Status: {}/{}".format(len(recoveries), total))
                gevent.sleep(2)

        u = self.spawn(updater)

        try:
            for channel in channels:
                pool.wait_available()
                r = Recovery(self.log, channel, start_at)
                pool.spawn(r.run)
                recoveries.append(r)
        finally:
            pool.join()
            u.kill()

        msg.edit(":ok_hand: Recovery Completed ({} total messages)".format(
            sum([i._recovered for i in recoveries])
        ))

    @Plugin.command("backfill channel", "[channel:snowflake]", level=-1, global_=True)
    def command_backfill_channel(self, event, channel=None):
        channel = self.state.channels.get(channel) if channel else event.channel
        backfill_channel.queue(channel.id)
        raise CommandSuccess("Enqueued channel to be backfilled")

    @Plugin.command("backfill guild", "[guild:guild] [concurrency:int]", level=-1, global_=True)
    def command_backfill_guild(self, event, guild=None, concurrency=1):
        guild = guild or event.guild
        backfill_guild.queue(guild.id)
        raise CommandSuccess("Enqueued guild to be backfilled")

    @Plugin.command("usage", "<word:str> [amount:int] [unit:str]", level=-1, group="words")
    def words_usage(self, event, word, amount=7, unit="days"):
        sql = """
            SELECT date, coalesce(count, 0) AS count
            FROM
                generate_series(
                    NOW() - interval %s,
                    NOW(),
                    %s
                ) AS date
            LEFT OUTER JOIN (
                SELECT date_trunc(%s, timestamp) AS dt, count(*) AS count
                FROM messages
                WHERE
                    timestamp >= (NOW() - interval %s) AND
                    timestamp < (NOW()) AND
                    guild_id=%s AND
                    (SELECT count(*) FROM regexp_matches(content, %s)) >= 1
                GROUP BY dt
            ) results
            ON (date_trunc(%s, date) = results.dt);
        """

        msg = event.msg.reply(":alarm_clock: One moment pls...")

        start = time.time()
        tuples = list(Message.raw(
            sql,
            "{} {}".format(amount, unit),
            "1 {}".format(unit),
            unit,
            "{} {}".format(amount, unit),
            event.guild.id,
            "{}".format(word),
            unit
        ).tuples())
        sql_duration = time.time() - start

        start = time.time()
        chart = pygal.Line(style=DiscordStyle)
        chart.title = 'Usage of "{}" over {} {}'.format(
            word, amount, unit,
        )

        if unit == "days":
            chart.x_labels = [i[0].strftime("%a %d") for i in tuples]
        elif unit == "minutes":
            chart.x_labels = [i[0].strftime("%X") for i in tuples]
        else:
            chart.x_labels = [i[0].strftime("%x %X") for i in tuples]

        chart.x_labels = [i[0] for i in tuples]
        chart.add(word, [i[1] for i in tuples])

        pngdata = cairosvg.svg2png(
            bytestring=chart.render(),
            dpi=72)
        chart_duration = time.time() - start

        event.msg.reply(
            "_SQL: {}ms_ - _Chart: {}ms_".format(
                int(sql_duration * 1000),
                int(chart_duration * 1000),
            ),
            attachments=[("chart.png", pngdata)])
        msg.delete()

    @Plugin.command("top", "<target:user|channel|guild>", level=-1, group="words")
    def words_top(self, event, target):
        if isinstance(target, DiscoUser):
            q = "author_id"
        elif isinstance(target, DiscoChannel):
            q = "channel_id"
        elif isinstance(target, DiscoGuild):
            q = "guild_id"
        else:
            raise Exception("You should not be here")

        sql = r"""
            SELECT word, count(*)
            FROM (
                SELECT regexp_split_to_table(content, "\s") as word
                FROM messages
                WHERE {}=%s
                LIMIT 3000000
            ) t
            GROUP BY word
            ORDER BY 2 DESC
            LIMIT 30
        """.format(q)

        t = MessageTable()
        t.set_header("Word", "Count")

        for word, count in Message.raw(sql, target.id).tuples():
            if "```" in word:
                continue
            t.add(word, count)

        event.msg.reply(t.compile())


class Recovery(object):
    def __init__(self, log, channel, start_dt, end_dt=None):
        self.log = log
        self.channel = channel
        self.start_dt = start_dt
        self.end_dt = end_dt or datetime.utcnow()
        self._recovered = 0

    def run(self):
        self.log.info("Starting recovery on channel %s (%s -> %s)", self.channel.id, self.start_dt, self.end_dt)

        msgs = self.channel.messages_iter(
            bulk=True,
            direction=MessageIterator.Direction.DOWN,
            after=str(from_datetime(self.start_dt))
        )

        for chunk in msgs:
            if not chunk:
                break

            for msg in chunk:
                if msg.author.bot:
                    break

            self._recovered += len(Message.from_disco_message_many(chunk, safe=True))

            if to_datetime(chunk[-1].id) > self.end_dt:
                break


class Backfill(object):
    def __init__(self, plugin, channel):
        self.log = plugin.log
        self.channel = channel

        self._scanned = 0
        self._inserted = 0

    def run(self):
        self.log.info("Starting backfill on channel %s", self.channel)

        msgs_iter = self.channel.messages_iter(bulk=True, after=1, direction=MessageIterator.Direction.DOWN)
        for chunk in msgs_iter:
            if not chunk:
                break

            for msg in chunk:
                if msg.author.bot:
                    break

                if not msg.channel.type == ChannelType.DM:
                    if not msg.channel.get_permissions(351776065477279745).can(Permissions.SEND_MESSAGES, Permissions.VIEW_CHANNEL):
                        break

            self._scanned += len(chunk)
            self._inserted = len(Message.from_disco_message_many(chunk, safe=True))
