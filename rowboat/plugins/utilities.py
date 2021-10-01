import operator
import random
from collections import defaultdict
from datetime import datetime, timedelta
from functools import reduce
from io import BytesIO

import gevent
import humanize
import requests
from PIL import Image
from disco.api.http import APIException
from disco.types.message import MessageEmbed
from disco.types.user import ActivityTypes, Status
from disco.types.user import User as DiscoUser
from disco.util.sanitize import S
from disco.util.snowflake import to_datetime
from gevent.pool import Pool
from peewee import fn

from rowboat.constants import (
    STATUS_EMOJI, BADGE_EMOJI, SNOOZE_EMOJI, GREEN_TICK_EMOJI, GREEN_TICK_EMOJI_ID,
    EMOJI_RE, USER_MENTION_RE, YEAR_IN_SEC, CDN_URL, WEB_URL
)
from rowboat.models.guild import GuildVoiceSession
from rowboat.models.message import Message, Reminder
from rowboat.models.user import User, Infraction
from rowboat.plugins import RowboatPlugin as Plugin, CommandFail, CommandSuccess
from rowboat.types.plugin import PluginConfig
from rowboat.util.badges import UserFlags
from rowboat.util.images import get_dominant_colors_user, get_dominant_colors_guild
from rowboat.util.input import parse_duration
from rowboat.util.timing import Eventual


def get_status_emoji(presence):
    if presence.activity and presence.activity.type == ActivityTypes.STREAMING:
        return STATUS_EMOJI[ActivityTypes.STREAMING], 'Streaming'
    elif presence.status == Status.ONLINE:
        return STATUS_EMOJI[Status.ONLINE], 'Online'
    elif presence.status == Status.IDLE:
        return STATUS_EMOJI[Status.IDLE], 'Idle',
    elif presence.status == Status.DND:
        return STATUS_EMOJI[Status.DND], 'DND'
    elif presence.status in (Status.OFFLINE, Status.INVISIBLE):
        return STATUS_EMOJI[Status.OFFLINE], 'Offline'


def get_emoji_url(emoji):
    return CDN_URL.format('-'.join(
        char.encode("unicode_escape").decode("utf-8")[2:].lstrip("0")
        for char in emoji))


class UtilitiesConfig(PluginConfig):
    pass


@Plugin.with_config(UtilitiesConfig)
class UtilitiesPlugin(Plugin):
    def load(self, ctx):
        super(UtilitiesPlugin, self).load(ctx)
        self.reminder_task = Eventual(self.trigger_reminders)
        self.spawn_later(10, self.queue_reminders)

    def queue_reminders(self):
        try:
            next_reminder = Reminder.select().order_by(
                Reminder.remind_at.asc()
            ).limit(1).get()
        except Reminder.DoesNotExist:
            return

        self.reminder_task.set_next_schedule(next_reminder.remind_at)

    @Plugin.command('coin', group='random', global_=True)
    def coin(self, event):
        """
        Flip a coin
        """
        raise CommandSuccess(random.choice(['heads', 'tails']))

    @Plugin.command('number', '[end:int] [start:int]', group='random', global_=True)
    def random_number(self, event, end=10, start=0):
        """
        Returns a random number
        """

        # Because someone will be an idiot
        if end > 9223372036854775807:
            raise CommandSuccess('Ending number too big!')

        if end <= start:
            raise CommandSuccess('Ending number must be larger than starting number!')

        raise CommandSuccess(str(random.randint(start, end)))

    @Plugin.command('cat', global_=True)
    def cat(self, event):
        try:
            r = requests.get('https://api.thecatapi.com/v1/images/search?format=src')
            r.raise_for_status()
            ext = r.headers['content-type'].split('/')[-1].split(';')[0]
            event.msg.reply('', attachments=[('cat.{}'.format(ext), r.content)])
        except:
            return event.msg.reply('{} Cat not found :('.format(r.status_code))

    @Plugin.command('dog', global_=True)
    def dog(self, event):
        try:
            r = requests.get('https://api.thedogapi.com/v1/images/search?format=src')
            r.raise_for_status()
            ext = r.headers['content-type'].split('/')[-1].split(';')[0]
            event.msg.reply('', attachments=[('dog.{}'.format(ext), r.content)])
        except Exception as e:
            return event.msg.reply(e.with_traceback + ' Dog not found :(')

    @Plugin.command('emoji', '<emoji:str>', global_=True)
    def emoji(self, event, emoji):
        if not EMOJI_RE.match(emoji):
            raise CommandFail('Unknown emoji: `{}`'.format(emoji))

        fields = []

        name, eid = EMOJI_RE.findall(emoji)[0]
        fields.append('**ID:** {}'.format(eid))
        fields.append('**Name:** {}'.format(S(name)))

        guild = self.state.guilds.find_one(lambda v: eid in v.emojis)
        if guild:
            fields.append('**Guild:** {} ({})'.format(S(guild.name), guild.id))

        url = 'https://cdn.discordapp.com/emojis/{}.png?v=1'.format(eid)
        r = requests.get(url)
        r.raise_for_status()
        return event.msg.reply('\n'.join(fields), attachments=[('emoji.png', r.content)])

    @Plugin.command('jumbo', '<emojis:str...>', global_=True)
    def jumbo(self, event, emojis):
        urls = []

        for emoji in emojis.split(' ')[:5]:
            if EMOJI_RE.match(emoji):
                _, eid = EMOJI_RE.findall(emoji)[0]
                urls.append('https://cdn.discordapp.com/emojis/{}.png?v=1'.format(eid))
            else:
                urls.append(get_emoji_url(emoji))

        width, height, images = 0, 0, []

        for r in Pool(6).imap(requests.get, urls):
            try:
                r.raise_for_status()
            except requests.HTTPError:
                return

            img = Image.open(BytesIO(r.content))
            height = img.height if img.height > height else height
            width += img.width + 10
            images.append(img)

        image = Image.new('RGBA', (width, height))
        width_offset = 0
        for img in images:
            image.paste(img, (width_offset, 0))
            width_offset += img.width + 10

        combined = BytesIO()
        image.save(combined, 'png', quality=55)
        combined.seek(0)
        return event.msg.reply('', attachments=[('emoji.png', combined)])

    @Plugin.command('seen', '<user:user>', global_=True)
    def seen(self, event, user):
        try:
            msg = Message.select(Message.timestamp).where(
                Message.author_id == user.id
            ).order_by(Message.timestamp.desc()).limit(1).get()
        except Message.DoesNotExist:
            raise CommandFail("I've never seen {}".format(user))

        raise CommandSuccess('I last saw {} {} (at {})'.format(
            user,
            humanize.naturaltime(datetime.utcnow() - msg.timestamp),
            msg.timestamp.strftime("%Y-%m-%d %H:%m:%S")
        ))

    @Plugin.command('search', '<query:str...>', global_=True)
    def search(self, event, query):
        queries = []

        if query.isdigit():
            queries.append((User.user_id == query))

        q = USER_MENTION_RE.findall(query)
        if len(q) and q[0].isdigit():
            queries.append((User.user_id == q[0]))
        else:
            queries.append((User.username ** '%{}%'.format(query.replace('%', ''))))

        if '#' in query:
            username, discrim = query.rsplit('#', 1)
            if discrim is not None:
                queries.append((
                    (User.username == username) &
                    (User.discriminator == discrim)))

        users = User.select().where(reduce(operator.or_, queries)).limit(10)
        if len(users) == 0:
            raise CommandFail('No users found for query `{}`'.format(S(query, escape_codeblocks=True)))

        if len(users) == 1:
            if users[0].user_id in self.state.users:
                return self.info(event, self.state.users.get(users[0].user_id))

        raise CommandSuccess('Found the following users for your query: ```{}```'.format(
            '\n'.join(['{} ({})'.format(str(i), i.user_id) for i in users[:25]])
        ))

    @Plugin.command('server', '[guild_id:snowflake]', aliases=['guild'], global_=True)
    def server(self, event, guild_id=None):
        guild = self.state.guilds.get(guild_id) if guild_id else event.guild
        if not guild:
            raise CommandFail('Invalid server')

        content = []
        content.append('**\u276F Server Information**')
        content.append('Owner: {} ({})'.format(
            guild.owner,
            guild.owner.id
        ))

        created_at = to_datetime(guild.id)
        content.append('Created: {} ({})'.format(
            humanize.naturaltime(datetime.utcnow() - created_at),
            created_at.isoformat(),
        ))

        content.append('Members: {:,}'.format(len(guild.members)))
        if guild.features:
            content.append('Features: {}'.format(', '.join(guild.features)))

        content.append('\n**\u276F Counts**')
        text_count = sum(1 for c in list(guild.channels.values()) if not c.is_voice)
        voice_count = len(guild.channels) - text_count
        content.append('Roles: {}'.format(len(guild.roles)))
        content.append('Text: {}'.format(text_count))
        content.append('Voice: {}'.format(voice_count))

        #content.append('\n**\u276F Members**')
        #status_counts = defaultdict(int)
        #for member in list(guild.members.values()):
        #    if not member.user.presence:
        #        status = Status.OFFLINE
        #    else:
        #        status = member.user.presence.status
        #    status_counts[status] += 1

        #for status, count in sorted(list(status_counts.items()), key=lambda i: str(i[0]), reverse=True):
        #    content.append('<{}> - {}'.format(
        #        STATUS_EMOJI[status], count
        #    ))

        embed = MessageEmbed()
        if guild.icon:
            embed.set_thumbnail(url=guild.icon_url)
            embed.color = get_dominant_colors_guild(guild)
        embed.description = '\n'.join(content)
        event.msg.reply('', embed=embed)

    @Plugin.command('info', '[user:user|snowflake]', aliases='whois')
    def info(self, event, user: User=None):
        if not user:
            user = event.author
        else:
            if not isinstance(user, DiscoUser):
                try:
                    user = self.state.guilds[event.guild.id].members[user].user
                except KeyError:
                    try:
                        user = self.state.users[user]
                    except KeyError:
                        try:
                            user = self.bot.client.api.users_get(user)
                        except APIException:
                            return event.msg.reply(':eyes: User not found').after(3).delete()

        self.client.api.channels_typing(event.channel.id)

        content = []
        content.append('**\u276F User Information**')
        content.append('Profile: <@{}>'.format(user.id))

        created_dt = to_datetime(user.id)
        content.append('Created: {} ({})'.format(
            humanize.naturaltime(datetime.utcnow() - created_dt),
            created_dt.strftime("%b %d %Y %H:%M:%S")
        ))

        member = event.guild.get_member(user.id) if event.guild else None

        #if user.presence:  # I couldn't get this to work w/o it lol
        #    emoji, status = get_status_emoji(user.presence)
        #    content.append('Status: <{}> {}'.format(emoji, status))
        #    if user.presence.activity and user.presence.activity.name:
        #        if user.presence.activity.type is ActivityTypes.DEFAULT:
        #            content.append('{}'.format(user.presence.activity.name))
        #        if user.presence.activity.type is ActivityTypes.STREAMING:
        #            content.append('Streaming: [{}]({})'.format(user.presence.activity.name, user.presence.activity.url))
        #        if user.presence.activity.type is ActivityTypes.LISTENING:
        #            content.append('Listening to {} on Spotify'.format(user.presence.activity.details))
        #        if user.presence.activity.type is ActivityTypes.WATCHING:
        #            content.append('Watching: {}'.format(user.presence.activity.name))
        #        if user.presence.activity.type is ActivityTypes.CUSTOM:
        #            content.append('Custom Status: {}'.format(user.presence.activity.state))
        #        if user.presence.activity.type is ActivityTypes.COMPETING:
        #            content.append('Competing: {}'.format(user.presence.activity.name))

        if user.public_flags:
            badges = ''
            user_badges = list(UserFlags(user.public_flags))
            for badge in user_badges:
                badges += '<{}> '.format(BADGE_EMOJI[badge])

            content.append('Badges: {}'.format(badges))

        if member:
            content.append('\n**\u276F Member Information**')

            if member.nick:
                content.append('Nickname: {}'.format(member.nick))

            content.append('Joined: {} ago ({})'.format(
                humanize.naturaldelta(datetime.utcnow() - member.joined_at),
                member.joined_at.strftime("%b %d %Y %H:%M:%S"),
            ))

            if member.roles:
                content.append('Roles: {}'.format(
                    ', '.join(('<@&{}>'.format(r) for r in member.roles))
                ))

        # Execute a bunch of queries
        newest_msg = Message.select(fn.MAX(Message.id)).where(
            (Message.author_id == user.id) &
            (Message.guild_id == event.guild.id)
        ).tuples()[0][0]

        # oldest_msg = Message.select(fn.MIN(Message.id)).where(
        #    (Message.author_id == user.id) & 
        #    (Message.guild_id == event.guild.id)
        # ).tuples()[0][0] #Slow Query

        voice = GuildVoiceSession.select(fn.COUNT(GuildVoiceSession.user_id),
            fn.SUM(GuildVoiceSession.ended_at - GuildVoiceSession.started_at)).where(
                (GuildVoiceSession.user_id == user.id) & (~(GuildVoiceSession.ended_at >> None)) & (
                    GuildVoiceSession.guild_id == event.guild.id)).tuples()[0]

        infractions = Infraction.select(Infraction.id).where(
            (Infraction.user_id == user.id) & (Infraction.guild_id == event.guild.id)).tuples()

        if newest_msg:
            content.append('\n **\u276F Activity**')
            content.append('Last Message: {} ({})'.format(
                humanize.naturaltime(datetime.utcnow() - to_datetime(newest_msg)),
                to_datetime(newest_msg).strftime("%b %d %Y %H:%M:%S"),
            ))
            # content.append('First Message: {} ({})'.format(
            #    humanize.naturaltime(datetime.utcnow() - to_datetime(oldest_msg)),
            #    to_datetime(oldest_msg).strftime("%b %d %Y %H:%M:%S"),
            # ))

        if len(infractions) > 0:
            content.append('\n**\u276F Infractions**')
            total = len(infractions)
            content.append('Total Infractions: **{:,}**'.format(total))

        if voice[0]:
            content.append('\n**\u276F Voice**')
            content.append('Sessions: `{:,}`'.format(voice[0]))
            content.append('Time: `{}`'.format(str(humanize.naturaldelta(
                voice[1]
            )).title()))

        embed = MessageEmbed()

        try:
            avatar = User.with_id(user.id).get_avatar_url()
        except:
            avatar = user.get_avatar_url()  # This fails if the user has never been seen by speedboat.

        embed.set_author(name='{} ({})'.format(
            str(user),
            user.id,
        ), icon_url=avatar)

        embed.set_thumbnail(url=avatar)

        embed.description = '\n'.join(content)
        embed.color = get_dominant_colors_user(user, avatar)
        event.msg.reply('', embed=embed)

    @Plugin.command('config', global_=True)
    def config_cmd(self, event):
        raise CommandSuccess('{}/guilds/{}/config'.format(WEB_URL, event.guild.id))

    def trigger_reminders(self):
        reminders = Reminder.with_message_join().where(
            (Reminder.remind_at < (datetime.utcnow() + timedelta(seconds=1)))
        )

        waitables = []
        for reminder in reminders:
            waitables.append(self.spawn(self.trigger_reminder, reminder))

        for waitable in waitables:
            waitable.join()

        self.queue_reminders()

    def trigger_reminder(self, reminder):
        message = Message.get(reminder.message_id)
        channel = self.state.channels.get(message.channel_id)
        if not channel:
            self.log.warning('Not triggering reminder, channel %s was not found!',
                message.channel_id)
            reminder.delete_instance()
            return

        msg = channel.send_message('<@{}> you asked me at {} ({}) to remind you about: {}'.format(
            message.author_id,
            reminder.created_at,
            humanize.naturaltime(datetime.utcnow() - reminder.created_at),
            S(reminder.content)
        ), allowed_mentions={'users': [str(message.author_id)]})

        # Add the emoji options
        msg.add_reaction(SNOOZE_EMOJI)
        msg.add_reaction(GREEN_TICK_EMOJI)

        try:
            mra_event = self.wait_for_event(
                'MessageReactionAdd',
                message_id=msg.id,
                conditional=lambda e: (
                    (e.emoji.name == SNOOZE_EMOJI or e.emoji.id == GREEN_TICK_EMOJI_ID) and
                    e.user_id == message.author_id
                )
            ).get(timeout=30)
        except gevent.Timeout:
            reminder.delete_instance()
            return
        finally:
            # Cleanup
            msg.delete_reaction(SNOOZE_EMOJI)
            msg.delete_reaction(GREEN_TICK_EMOJI)

        if mra_event.emoji.name == SNOOZE_EMOJI:
            reminder.remind_at = datetime.utcnow() + timedelta(minutes=20)
            reminder.save()
            msg.edit('Ok, I\'ve snoozed that reminder for 20 minutes.')
            return

        reminder.delete_instance()

    @Plugin.command('clear', group='r', global_=True)
    def cmd_remind_clear(self, event):
        count = Reminder.delete_for_user(event.author.id)
        raise CommandSuccess('I cleared {} reminders for you'.format(count))

    @Plugin.command('add', '<duration:str> <content:str...>', group='r', global_=True)
    @Plugin.command('remind', '<duration:str> <content:str...>', global_=True)
    def cmd_remind(self, event, duration, content):
        if Reminder.count_for_user(event.author.id) > 15:
            raise CommandFail('You can only have 15 reminders going at once!')

        remind_at = parse_duration(duration)
        if remind_at > (datetime.utcnow() + timedelta(seconds=5 * YEAR_IN_SEC)):
            raise CommandSuccess('Thats too far in the future, I\'ll forget!')

        r = Reminder.create(
            message_id=event.msg.id,
            remind_at=remind_at,
            content=content
        )
        self.reminder_task.set_next_schedule(r.remind_at)
        raise CommandSuccess('I\'ll remind you at {} ({})'.format(
            r.remind_at.isoformat(),
            humanize.naturaldelta(r.remind_at - datetime.utcnow()),
        ))
