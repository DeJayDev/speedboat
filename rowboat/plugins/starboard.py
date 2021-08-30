from datetime import datetime, timedelta

import peewee
from disco.api.http import APIException
from disco.bot import CommandLevels
from disco.types.message import ActionRow, ButtonStyles, ComponentTypes, MessageEmbed
from peewee import fn, JOIN

from rowboat.constants import STAR_EMOJI, ERR_UNKNOWN_MESSAGE
from rowboat.models.message import StarboardEntry, Message
from rowboat.models.user import StarboardBlock, User
from rowboat.plugins import RowboatPlugin as Plugin, CommandFail, CommandSuccess
from rowboat.types import ChannelField, Field, SlottedModel, ListField, DictField
from rowboat.types.plugin import PluginConfig
from rowboat.util.timing import Debounce


def is_star_event(e):
    if e.emoji.name == STAR_EMOJI:
        return True


class ChannelConfig(SlottedModel):
    sources = ListField(ChannelField, default=[])

    # Delete the star when the message is deleted
    clear_on_delete = Field(bool, default=True)

    # Min number of stars to post on the board
    min_stars = Field(int, default=1)
    min_stars_pin = Field(int, default=15)

    # The number which represents the "max" star level
    star_color_max = Field(int, default=15)

    # Prevent users from starring their own posts
    prevent_self_star = Field(bool, default=False)

    def get_color(self, count):
        ratio = min(count / float(self.star_color_max), 1.0)

        return (
            (255 << 16) +
            (int((194 * ratio) + (253 * (1 - ratio))) << 8) +
            int((12 * ratio) + (247 * (1 - ratio))))


class StarboardConfig(PluginConfig):
    channels = DictField(ChannelField, ChannelConfig)

    # TODO: validate that each source channel has only one starboard mapping

    def get_board(self, channel_id):
        # Starboards can't work recursively
        if channel_id in self.channels:
            return None, None

        for starboard, config in list(self.channels.items()):
            if not config.sources or channel_id in config.sources:
                return starboard, config
        return None, None


@Plugin.with_config(StarboardConfig)
class StarboardPlugin(Plugin):
    def load(self, ctx):
        super(StarboardPlugin, self).load(ctx)
        self.updates = {}
        self.locks = {}

    @Plugin.command('show', '<mid:snowflake>', group='stars', level=CommandLevels.TRUSTED)
    def stars_show(self, event, mid):
        try:
            star = StarboardEntry.select().join(Message).where(
                (Message.guild_id == event.guild.id) &
                (~(StarboardEntry.star_message_id >> None)) &
                (
                    (Message.id == mid) |
                    (StarboardEntry.star_message_id == mid)
                )
            ).get()
        except StarboardEntry.DoesNotExist:
            raise CommandFail('No starboard message with that id')

        _, sb_config = event.config.get_board(star.message.channel_id)

        try:
            source_msg = self.client.api.channels_messages_get(
                star.message.channel_id,
                star.message_id)
        except:
            raise CommandFail('No starboard message with that id')

        content, embed, row = self.get_embed(star, source_msg, sb_config)
        event.msg.reply(content, embed=embed, components=[row.to_dict()])

    @Plugin.command('stats', '[user:user]', group='stars', level=CommandLevels.MOD)
    def stars_stats(self, event, user=None):
        if user:
            try:
                given_stars = list(StarboardEntry.select(
                    fn.COUNT('*'),
                ).join(Message).where(
                    (~ (StarboardEntry.star_message_id >> None)) &
                    (StarboardEntry.stars.contains(user.id)) &
                    (Message.guild_id == event.guild.id)
                ).tuples())[0][0]

                recieved_stars_posts, recieved_stars_total = list(StarboardEntry.select(
                    fn.COUNT('*'),
                    fn.SUM(fn.array_length(StarboardEntry.stars, 1)),
                ).join(Message).where(
                    (~ (StarboardEntry.star_message_id >> None)) &
                    (Message.author_id == user.id) &
                    (Message.guild_id == event.guild.id)
                ).tuples())[0]
            except:
                raise CommandFail('Failed to crunch the numbers on that user')

            embed = MessageEmbed()
            embed.color = 0xFEE75C
            embed.title = user.username
            embed.set_thumbnail(url=user.avatar_url)
            embed.add_field(name='Total Stars Given', value=str(given_stars), inline=True)
            embed.add_field(name='Total Posts w/ Stars', value=str(recieved_stars_posts), inline=True)
            embed.add_field(name='Total Stars Recieved', value=str(recieved_stars_total), inline=True)
            # embed.add_field(name='Star Rank', value='#{}'.format(recieved_stars_rank), inline=True)
            return event.msg.reply('', embed=embed)

        total_starred_posts, total_stars = list(StarboardEntry.select(
            fn.COUNT('*'),
            fn.SUM(fn.array_length(StarboardEntry.stars, 1)),
        ).join(Message).where(
            (~ (StarboardEntry.star_message_id >> None)) &
            (StarboardEntry.blocked == 0) &
            (Message.guild_id == event.guild.id)
        ).tuples())[0]

        top_users = list(StarboardEntry.select(fn.SUM(fn.array_length(StarboardEntry.stars, 1)), User.user_id).join(
            Message,
        ).join(
            User,
            on=(Message.author_id == User.user_id),
        ).where(
            (~ (StarboardEntry.star_message_id >> None)) &
            (fn.array_length(StarboardEntry.stars, 1) > 0) &
            (StarboardEntry.blocked == 0) &
            (Message.guild_id == event.guild.id)
        ).group_by(User).order_by(fn.SUM(fn.array_length(StarboardEntry.stars, 1)).desc()).limit(5).tuples())

        embed = MessageEmbed()
        embed.color = 0xFEE75C
        embed.title = 'Star Stats'
        embed.add_field(name='Total Stars Given', value=total_stars, inline=True)
        embed.add_field(name='Total Starred Posts', value=total_starred_posts, inline=True)
        embed.add_field(name='Top Star Recievers', value='\n'.join(
            '{}. <@{}> ({})'.format(idx + 1, row[1], row[0]) for idx, row in enumerate(top_users)
        ))
        event.msg.reply('', embed=embed)

    @Plugin.command('check', '<mid:snowflake>', group='stars', level=CommandLevels.ADMIN)
    def stars_update(self, event, mid):
        try:
            entry = StarboardEntry.select(StarboardEntry, Message).join(
                Message
            ).where(
                (Message.guild_id == event.guild.id) &
                (StarboardEntry.message_id == mid)
            ).get()
        except StarboardEntry.DoesNotExist:
            raise CommandFail('No starboard entry exists with that message id')

        msg = self.client.api.channels_messages_get(
            entry.message.channel_id,
            entry.message_id)

        users = [i.id for i in msg.get_reactors(STAR_EMOJI)]

        if set(users) != set(entry.stars):
            StarboardEntry.update(
                stars=users,
                dirty=True
            ).where(
                (StarboardEntry.message_id == entry.message_id)
            ).execute()
        else:
            StarboardEntry.update(
                dirty=True
            ).where(
                (StarboardEntry.message_id == mid)
            ).execute()

        self.queue_update(event.guild.id, event.config)
        raise CommandSuccess('Forcing an update on message {}'.format(mid))

    @Plugin.command('block', '<entity:user|channel>', group='stars', level=CommandLevels.MOD)
    def stars_block(self, event, entity):
        _, created = StarboardBlock.get_or_create(
            guild_id=event.guild.id,
            user_id=entity.id,
            defaults={
                'actor_id': event.author.id,
            })

        if not created:
            raise CommandFail('{} is already not allowed on the starboard'.format(
                entity,
            ))

        # Update the starboard, remove stars and posts
        StarboardEntry.block(entity.id)

        # Finally, queue an update for the guild
        self.queue_update(event.guild.id, event.config)

        raise CommandSuccess('Disallowed {} from the starboard'.format(
            entity,
        ))

    @Plugin.command('unblock', '<entity:user|channel>', group='stars', level=CommandLevels.MOD)
    def stars_unblock(self, event, entity):
        count = StarboardBlock.delete().where(
            (StarboardBlock.guild_id == event.guild.id) &
            (StarboardBlock.entity_id == entity.id)
        ).execute()

        if not count:
            raise CommandFail('{} is already allowed on the starboard'.format(
                entity,
            ))

        # Reenable posts and stars for this user
        StarboardEntry.unblock(entity.id)

        # Finally, queue an update for the guild
        self.queue_update(event.guild.id, event.config)

        raise CommandSuccess('Allowed {} on the starboard'.format(
            entity,
        ))

    @Plugin.command('unhide', '<mid:snowflake>', group='stars', level=CommandLevels.MOD)
    def stars_unhide(self, event, mid):
        count = StarboardEntry.update(
            blocked=False,
            dirty=True,
        ).where(
            (StarboardEntry.message_id == mid) &
            (StarboardEntry.blocked == 1)
        ).execute()

        if not count:
            raise CommandFail('No hidden starboard message with that ID')

        self.queue_update(event.guild.id, event.config)
        raise CommandSuccess('Message {} has been unhidden from the starboard'.format(
            mid,
        ))

    @Plugin.command('hide', '<mid:snowflake>', group='stars', level=CommandLevels.MOD)
    def stars_hide(self, event, mid):
        count = StarboardEntry.update(
            blocked=True,
            dirty=True,
        ).where(
            (StarboardEntry.message_id == mid)
        ).execute()

        if not count:
            raise CommandFail('No starred message with that ID')

        self.queue_update(event.guild.id, event.config)
        raise CommandSuccess('Message {} has been hidden from the starboard'.format(
            mid,
        ))

    @Plugin.command('update', group='stars', level=CommandLevels.ADMIN)
    def force_update_stars(self, event):
        # First, iterate over stars and repull their reaction count
        stars = StarboardEntry.select(StarboardEntry, Message).join(
            Message
        ).where(
            (Message.guild_id == event.guild.id) &
            (~ (StarboardEntry.star_message_id >> None))
        ).order_by(Message.timestamp.desc()).limit(100)

        info_msg = event.msg.reply('Updating starboard...')

        for star in stars:
            msg = self.client.api.channels_messages_get(
                star.message.channel_id,
                star.message_id)

            users = [i.id for i in msg.get_reactors(STAR_EMOJI)]

            if set(users) != set(star.stars):
                self.log.warning('star %s had outdated reactors list (%s vs %s)',
                    star.message_id,
                    len(users),
                    len(star.stars))

                StarboardEntry.update(
                    stars=users,
                    dirty=True,
                ).where(
                    (StarboardEntry.message_id == star.message_id)
                ).execute()

        self.queue_update(event.guild.id, event.config)
        info_msg.delete()
        event.msg.reply(':ballot_box_with_check: Starboard Updated!')

    @Plugin.command('lock', group='stars', level=CommandLevels.ADMIN)
    def lock_stars(self, event):
        if event.guild.id in self.locks:
            raise CommandFail('Starboard is already locked')

        self.locks[event.guild.id] = True
        raise CommandSuccess('Starboard has been locked')

    @Plugin.command('unlock', group='stars', level=CommandLevels.ADMIN)
    def unlock_stars(self, event):
        if event.guild.id in self.locks:
            del self.locks[event.guild.id]
            raise CommandSuccess('Starboard has been unlocked')

        raise CommandFail('Starboard is not locked')

    def queue_update(self, guild_id, config):
        if guild_id in self.locks:
            return

        if guild_id not in self.updates or not self.updates[guild_id].active():
            if guild_id in self.updates:
                del self.updates[guild_id]
            self.updates[guild_id] = Debounce(self.update_starboard, 2, 6, guild_id=guild_id, config=config.get())
        else:
            self.updates[guild_id].touch()

    def update_starboard(self, guild_id, config):
        # Grab all dirty stars that where posted in the last 32 hours
        stars = StarboardEntry.select().join(Message).where(
            (StarboardEntry.dirty == 1) &
            (Message.guild_id == guild_id) &
            (Message.timestamp > (datetime.utcnow() - timedelta(hours=32)))
        )

        for star in stars:
            sb_id, sb_config = config.get_board(star.message.channel_id)

            if not sb_id:
                StarboardEntry.update(dirty=False).where(StarboardEntry.message_id == star.message_id).execute()
                continue

            # If this star has no stars, delete it from the starboard
            if not star.stars:
                if not star.star_channel_id:
                    StarboardEntry.update(dirty=False).where(StarboardEntry.message_id == star.message_id).execute()
                    continue

                self.delete_star(star)
                continue

            # Grab the original message
            try:
                source_msg = self.client.api.channels_messages_get(
                    star.message.channel_id,
                    star.message_id)
            except:
                self.log.exception('Star message went missing %s / %s: ', star.message.channel_id, star.message_id)
                self.delete_star(star, update=True)
                continue

            # If we previously posted this in the wrong starboard, delete it
            if star.star_channel_id and (
                    star.star_channel_id != sb_id or
                    len(star.stars) < sb_config.min_stars) or star.blocked:
                self.delete_star(star, update=True)

            if len(star.stars) < sb_config.min_stars or star.blocked:
                StarboardEntry.update(dirty=False).where(StarboardEntry.message_id == star.message_id).execute()
                continue

            self.post_star(star, source_msg, sb_id, sb_config)

    def delete_star(self, star, update=True):
        try:
            self.client.api.channels_messages_delete(
                star.star_channel_id,
                star.star_message_id,
            )
        except:
            pass

        if update:
            StarboardEntry.update(
                dirty=False,
                star_channel_id=None,
                star_message_id=None,
            ).where(
                (StarboardEntry.message_id == star.message_id)
            ).execute()

            # Update this for post_star
            star.star_channel_id = None
            star.star_message_id = None

    def post_star(self, star, source_msg, starboard_id, config):
        # Generate the embed and post it
        content, embed, row = self.get_embed(star, source_msg, config)

        if not star.star_message_id:
            try:
                msg = self.client.api.channels_messages_create(
                        starboard_id,
                        content,
                        embed=embed,
                        components=[row.to_dict()])
            except:
                self.log.exception('Failed to post starboard message: ')
                return
        else:
            try:
                msg = self.client.api.channels_messages_modify(
                    star.star_channel_id,
                    star.star_message_id,
                    content,
                    embed=embed)
            except APIException as e:
                # If we get a 10008, assume this message was deleted
                if e.code == ERR_UNKNOWN_MESSAGE:
                    star.star_message_id = None
                    star.star_channel_id = None

                    # Recurse so we repost
                    return self.post_star(star, source_msg, starboard_id, config)

        # Update our starboard entry
        StarboardEntry.update(
            dirty=False,
            star_channel_id=msg.channel_id,
            star_message_id=msg.id,
        ).where(
            (StarboardEntry.message_id == star.message_id)
        ).execute()

    @Plugin.listen('MessageReactionAdd', conditional=is_star_event)
    def on_message_reaction_add(self, event):
        try:
            # Grab the message, and JOIN across blocks to check if a block exists
            #  for either the message author or the reactor.
            msg = Message.select(
                Message,
                StarboardBlock
            ).join(
                StarboardBlock,
                join_type=JOIN.LEFT_OUTER,
                on=(
                    (
                        (Message.author_id == StarboardBlock.entity_id) |
                        (Message.channel_id == StarboardBlock.entity_id) | # Shit naming, but it's the best I got
                        (StarboardBlock.entity_id == event.user_id)
                    ) &
                    (Message.guild_id == StarboardBlock.guild_id)
                )
            ).where(
                (Message.id == event.message_id)
            ).get()
        except Message.DoesNotExist:
            return

        # If either the reaction or message author is blocked, prevent this action
        try:
            if msg.starboardblock.entity_id:
                event.delete()
                return
        except AttributeError:
            pass  # /shrug

        # Check if the board prevents self stars
        sb_id, board = event.config.get_board(event.channel_id)
        if not sb_id:
            return

        if board.prevent_self_star and msg.author_id == event.user_id:
            event.delete()
            return

        try:
            StarboardEntry.add_star(event.message_id, event.user_id)
        except peewee.IntegrityError:
            msg = self.client.api.channels_messages_get(
                event.channel_id,
                event.message_id)

            if msg:
                Message.from_disco_message(msg)
                StarboardEntry.add_star(event.message_id, event.user_id)
            else:
                return

        self.queue_update(event.guild.id, event.config)

    @Plugin.listen('MessageReactionRemove', conditional=is_star_event)
    def on_message_reaction_remove(self, event):
        StarboardEntry.remove_star(event.message_id, event.user_id)
        self.queue_update(event.guild.id, event.config)

    @Plugin.listen('MessageReactionRemoveAll')
    def on_message_reaction_remove_all(self, event):
        StarboardEntry.update(
            stars=[],
            blocked_stars=[],
            dirty=True
        ).where(
            (StarboardEntry.message_id == event.message_id)
        ).execute()
        self.queue_update(event.guild.id, event.config)

    @Plugin.listen('MessageUpdate')
    def on_message_update(self, event):
        sb_id, sb_config = event.config.get_board(event.channel_id)
        if not sb_id:
            return

        count = StarboardEntry.update(
            dirty=True
        ).where(
            (StarboardEntry.message_id == event.message.id)
        ).execute()

        if count:
            self.queue_update(event.guild.id, event.config)

    @Plugin.listen('MessageDelete')
    def on_message_delete(self, event):
        sb_id, sb_config = event.config.get_board(event.channel_id)
        if not sb_id:
            return

        if sb_config.clear_on_delete:
            stars = list(StarboardEntry.delete().where(
                (StarboardEntry.message_id == event.id)
            ).returning(StarboardEntry).execute())

            for star in stars:
                self.delete_star(star, update=False)

    def get_embed(self, star, msg, config):
        # Create the 'header' (non-embed) text
        stars = ':star:'

        if len(star.stars) > 1:
            if len(star.stars) >= config.star_color_max:
                stars = ':star2:'
            stars = stars + ' {}'.format(len(star.stars))

        content = '**{}** <#{}> ({})'.format(
            stars,
            msg.channel_id,
            msg.id
        )

        # Generate embed section
        embed = MessageEmbed()
        embed.description ='{}'.format(msg.content)

        if msg.attachments:
            attach = list(msg.attachments.values())[0]
            if attach.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                embed.set_image(url=attach.url)

        if msg.embeds:
            if msg.embeds[0].image.url:
                embed.set_image(url=msg.embeds[0].image.url)
            elif msg.embeds[0].thumbnail.url:
                embed.set_image(url=msg.embeds[0].thumbnail.url)

        author = msg.guild.get_member(msg.author)
        if author:
            embed.set_author(
                name=author,
                icon_url=author.user.avatar_url
            )
        else:
            embed.set_author(
                name=msg.author,
                icon_url=msg.author.avatar_url)

        embed.timestamp = msg.timestamp.isoformat()
        embed.color = config.get_color(len(star.stars))

        row = ActionRow()
        row.add_component(label='Jump to Message', type=ComponentTypes.BUTTON, style=ButtonStyles.LINK, url='https://discord.com/channels/{}/{}/{}'.format(
            msg.guild.id,
            msg.channel_id,
            msg.id
        ))

        return content, embed, row
