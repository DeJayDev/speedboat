import operator
import random
from datetime import datetime, timedelta
from functools import reduce
from io import BytesIO

import gevent
import pytz
import requests
from disco.api.http import APIException
from disco.types.guild import Guild
from disco.types.message import (MessageEmbed, MessageEmbedAuthor,
                                 MessageEmbedField, MessageReference)
from disco.types.user import ActivityTypes, Status
from disco.types.user import User as DiscoUser
from disco.util.sanitize import S
from disco.util.snowflake import to_datetime
from gevent.pool import Pool
from peewee import DoesNotExist, fn
from PIL import Image

from rowboat.constants import (BADGE_EMOJI, CDN_URL, EMOJI_RE,
                               GREEN_TICK_EMOJI, GREEN_TICK_EMOJI_ID,
                               SNOOZE_EMOJI, STATUS_EMOJI, USER_MENTION_RE,
                               WEB_URL, YEAR_IN_SEC)
from rowboat.models.message import Message, Reminder
from rowboat.models.user import Infraction, User
from rowboat.plugins import CommandFail, CommandSuccess
from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.types.plugin import PluginConfig
from rowboat.util.badges import UserFlags
from rowboat.util.images import (get_dominant_colors_guild,
                                 get_dominant_colors_user)
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
        except DoesNotExist:
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

    @Plugin.command('cat', '{bentley}',global_=True)
    def cat(self, event, bentley=False):
        try:
            if bentley:
                URL = 'https://bentley.tadhg.sh/api/random'
                data = requests.get(URL).json()
                fname = 'bentley-' + str(data['id']) # Probably don't have to, but gonna.
                cat = requests.get(data['url'])
            else:
                URL = 'https://api.thecatapi.com/v1/images/search'
                data = requests.get(URL).json()
                fname = data[0]['id']
                cat = requests.get(data[0]['url'])
            cat.raise_for_status()
            fext = cat.headers['content-type'].split('/')[-1].split(';')[0]
            event.msg.reply('', attachments=[('cat-{}.{}'.format(fname, fext), cat.content)])
        except:
            return event.msg.reply('{} Cat not found :('.format(cat.status_code))

    @Plugin.command('otter', global_=True)
    def otter(self, event):
        try:
            URL = 'https://otter.bruhmomentlol.repl.co/random'
            otter = requests.get(URL)
            otter.raise_for_status()

            fext = otter.headers['x-file-ext'] 
            event.msg.reply('', attachments=[('otter.{}'.format(fext), otter.content)])
        except:
            return event.msg.reply('{} Otter not found :('.format(otter.status_code))

    @Plugin.command('dog', global_=True)
    def dog(self, event):
        try:
            URL = 'https://api.thedogapi.com/v1/images/search'
            data = requests.get(URL).json()
            dog = requests.get(data[0]['url'])
            dog.raise_for_status()

            fname = data[0]['id']
            fext = dog.headers['content-type'].split('/')[-1].split(';')[0]
            event.msg.reply('', attachments=[('dog-{}.{}'.format(fname, fext), dog.content)])
        except Exception as e:
            return event.msg.reply('{} Dog not found :('.format(dog.status_code))

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
    def seen(self, event, user: User):
        try:
            msg = Message.select(Message.timestamp).where(
                Message.author_id == user.id
            ).order_by(Message.timestamp.desc()).limit(1).get()
        except DoesNotExist:
            raise CommandFail("I've never seen {}".format(user))

        raise CommandSuccess('I last saw {} {}'.format(
            user,
            int(msg.timestamp.timestamp())
        ))

    @Plugin.command('search', '<query:str...>', global_=True)
    def search(self, event, query: str):
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
        guild: Guild = self.state.guilds.get(guild_id) if guild_id else event.guild
        if not guild:
            raise CommandFail('Invalid server')

        embed = MessageEmbed()
        embed.set_author(MessageEmbedAuthor(name=guild.name, icon_url=guild.icon_url()))

        # General Abouts
        about_field = MessageEmbedField()
        about_field.name = '**\u276F About**'
        about_text = 'Created by {} ({}) — <t:{}:R>'.format(guild.owner, guild.owner.id, int(to_datetime(guild.id).replace(tzinfo=pytz.UTC).timestamp()))
        about_text += '\nMembers: {:,}/{:,}'.format(guild.approximate_presence_count, guild.member_count)
        about_text += '\nRegion: {}'.format(guild.region)
        about_field.value = about_text
        embed.add_field(about_field)

        # General Counts
        counts_field = MessageEmbedField()
        counts_field.name = '\n**\u276F Counts**'
        text_count = sum(1 for c in list(guild.channels.values()) if not c.is_voice and not c.is_thread)
        voice_count = len(guild.channels) - text_count

        counts_field.value = 'Roles: {:,}\nText: {:,}\nVoice: {:,}'.format(len(guild.roles), text_count, voice_count)
        embed.add_field(counts_field)

        # Security
        security_field = MessageEmbedField()
        security_field.name = '\n**\u276F Security**'
        security_field.value = 'Verification: {}\nExplicit Content: {}'.format(
            guild.verification_level,
            guild.explicit_content_filter
        )
        embed.add_field(security_field)

        # Features
        features_field = MessageEmbedField()
        features_field.name = '\n**\u276F Features**'
        features_field.value = 'Features: {}'.format(', '.join(guild.features))
        embed.add_field(features_field)

        if guild.icon:
            embed.color = get_dominant_colors_guild(guild)
        event.msg.reply('', embed=embed)

    @Plugin.command('info', '[user:user|snowflake]', aliases='whois')
    def info(self, event, user: User = None):
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
        content.append('Created: <t:{0}:R> (<t:{0}:f>)'.format(
            int(created_dt.replace(tzinfo=pytz.UTC).timestamp())
        ))

        member = event.guild.get_member(user.id) if event.guild else None

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

            content.append('Joined: <t:{0}:R> (<t:{0}:f>)'.format(
                int(member.joined_at.replace(tzinfo=pytz.UTC).timestamp())
            ))
            
            content.append('Messages: {}'.format(
                int(Message.select(fn.Count(Message.id)).where(
                        (Message.author_id == user.id) &
                        (Message.guild_id == event.guild.id)
                   ).tuples()[0][0])
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

        infractions = Infraction.select(Infraction.id).where(
            (Infraction.user_id == user.id) & (Infraction.guild_id == event.guild.id)).tuples()

        if newest_msg:
            content.append('\n **\u276F Activity**')
            content.append('Last Message: <t:{0}:R> (<t:{0}:f>)'.format(
                int((to_datetime(newest_msg).replace(tzinfo=pytz.UTC)).timestamp())
            ))
            # content.append('First Message: {} ({})'.format(
            #    humanize.naturaltime(datetime.utcnow() - to_datetime(oldest_msg)),
            #    to_datetime(oldest_msg).strftime("%b %d %Y %H:%M:%S"),
            # ))

        if len(infractions) > 0:
            content.append('\n**\u276F Infractions**')
            total = len(infractions)
            content.append('Total Infractions: **{:,}**'.format(total))

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

    def trigger_reminder(self, reminder: Reminder):
        message = Message.get(reminder.message_id)
        channel = self.state.channels.get(message.channel_id)
        if not channel:
            self.log.warning('Not triggering reminder, channel %s was not found!',
                             message.channel_id)
            reminder.delete_instance()
            return

        msg = channel.send_message(
            '<@{}> you asked me on <t:{reminder_time}:f> (<t:{reminder_time}:R>) to remind you about: {}'.format(
                message.author_id,
                S(reminder.content),
                reminder_time=int(reminder.created_at.replace(tzinfo=pytz.UTC).timestamp()),
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
            try:
                msg.delete_all_reactions()
            except APIException: # We don't have permission to remove reactions, but, we don't want to fail the reminder.
                pass

        if mra_event.emoji.name == SNOOZE_EMOJI:
            reminder.remind_at = datetime.utcnow() + timedelta(minutes=20)
            reminder.save()
            msg.edit('Ok, I\'ve snoozed that reminder. You\'ll get another notification in 20 minutes.')
            return

        reminder.delete_instance()

    @Plugin.command('clear', group='r', global_=True)
    def cmd_remind_clear(self, event):
        count = Reminder.delete_for_user(event.author.id)
        raise CommandSuccess('I cleared {} reminders for you'.format(count))

    @Plugin.command('add', '<duration:str> [content:str...]', group='r', global_=True)
    @Plugin.command('remind', '<duration:str> [content:str...]', global_=True)
    def cmd_remind(self, event, duration, content=None):
        if Reminder.count_for_user(event.author.id) > 15:
            raise CommandFail('You can only have 15 reminders going at once!')

        remind_at = parse_duration(duration)
        if remind_at > (datetime.utcnow() + timedelta(seconds=5 * YEAR_IN_SEC)):
            raise CommandFail('That\'s too far in the future... I\'ll forget!')

        if event.msg.message_reference:
            referenced_msg: MessageReference = event.channel.get_message(event.msg.message_reference.message_id)
            content = 'https://discord.com/channels/{}/{}/{}'.format(
                self.state.channels.get(referenced_msg.channel_id).guild_id,
                referenced_msg.channel_id,
                referenced_msg.id)
        elif not content:
            raise CommandFail('You need to provide content for the reminder, or reply to a message!')

        r = Reminder.create(
            message_id=event.msg.id,
            remind_at=remind_at,
            content=content
        )
        self.reminder_task.set_next_schedule(r.remind_at)
        raise CommandSuccess('I\'ll remind you at <t:{0}:f> (<t:{0}:R>)'.format(
            int(r.remind_at.replace(tzinfo=pytz.UTC).timestamp())
        ))
