import datetime
from random import randint

import gevent
from disco.bot import CommandLevels
from disco.types.message import MessageTable
from disco.util.sanitize import S

from rowboat.constants import (GREEN_TICK_EMOJI, GREEN_TICK_EMOJI_ID,
                               RED_TICK_EMOJI, RED_TICK_EMOJI_ID)
from rowboat.models.guild import GuildMemberLevel
from rowboat.models.message import Message
from rowboat.models.user import User, XPBlock
from rowboat.plugins import CommandFail, CommandSuccess
from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.types import DictField, Field, SlottedModel, snowflake
from rowboat.types.plugin import PluginConfig


class LevelUpActionConfig(SlottedModel):
    message = Field(bool, default=False)
    chat = Field(bool, default=True)


class LevelPluginConfig(PluginConfig):
    actions = Field(LevelUpActionConfig)

    rewards = DictField(int, snowflake)
    pass


@Plugin.with_config(LevelPluginConfig)
class LevelPlugin(Plugin):

    def can_act_on(self, event, victim_id, throw=True):
        if event.author.id == victim_id:
            if not throw:
                return False
            raise CommandFail('Cannot execute that action on yourself')
    
    def level_from_xp(self, exp):
        def get_required_xp(level):
            return 5 * (level ** 2) + 50 * level + 100  # (5x^2)+500x

        level = 0

        while exp >= get_required_xp(level):
            exp -= get_required_xp(level)
            level += 1

        return level

    def try_levelup(self, event, level):
        if event.config.actions.message:
            event.channel.send_message(':ok_hand: You are now level {} in {}!'.format(
                level,
                event.guild.name
            ))
            
        if event.config.actions.chat:
            event.channel.send_message(S(':ok_hand: {} is now level {}!'.format(
                event.author,
                level
            )))

        if event.config.rewards:
            if event.config.rewards[level]:
                event.member.add_role(event.config.rewards[level], reason="Leveled Up!")

    @Plugin.listen('MessageCreate')
    def xp_message_send(self, event):
        if event.author.bot:
            return

        config = self.call('CorePlugin.get_config', event.guild.id)

        if config and config.commands:
            commands = list(self.bot.get_commands_for_message(
                config.commands.mention,
                {},
                config.commands.prefix if config.commands.prefix else config.commands.prefixes,
                event.message))
        
        if commands:
            return  # No XP for commands

        try:
            user = GuildMemberLevel.select(GuildMemberLevel, XPBlock).join(
                XPBlock,
                on=((GuildMemberLevel.guild_id == XPBlock.guild_id) &
                    (GuildMemberLevel.user_id == XPBlock.user_id))
            ).where(
                (GuildMemberLevel.user_id == event.author.id) &
                (GuildMemberLevel.guild_id == event.guild.id)
            ).get()

            last_message = Message.select(Message.timestamp).where(
                (Message.author_id == event.author.id) &
                (Message.guild_id == event.guild.id)
            ).order_by(Message.timestamp.desc()).limit(1).get()

            if user.xpblock:
                return  # No XP for blocked meanies >:(
            elif last_message.timestamp < datetime.timedelta(seconds=60):
                return  # Too fast.

        except GuildMemberLevel.DoesNotExist:
            user = GuildMemberLevel.create_new(event.guild.get_member(event.author.id)) # lol

        pre_level = self.level_from_xp(user.xp)
        new_xp = randint(15, 25)

        user.add_xp(event.guild.id, event.author.id, new_xp)
        new_level = self.level_from_xp(user.xp + new_xp)

        if new_level > pre_level:
            self.try_levelup(event, new_level)
  
    @Plugin.command('block', '<user:user|snowflake> [reason:str...]', group='xp', aliases=['mute', 'stfu'], level=CommandLevels.MOD)
    def xp_block(self, event, user, reason=None):
        member = event.guild.get_member(user)
        if member:
            self.can_act_on(event, member.id)
            _, created = XPBlock.get_or_create(
                guild_id = event.guild.id,
                user_id = user.id,
                defaults={
                    'actor_id': event.author.id,
                    'reason': reason or 'no reason'
                })
            
            if not created:
                raise CommandFail('{} is already blocked from gaining XP'.format(
                    user,
                ))
        else:
            raise CommandFail('Invalid user')

        raise CommandSuccess('Blocked {} from gaining XP.'.format(member))

    @Plugin.command('unblock', '<user:user|snowflake>', group='xp', aliases=['unmute'], level=CommandLevels.MOD)
    def xp_unblock(self, event, user):
        member = event.guild.get_member(user)
        if member:
            self.can_act_on(event, member.id)
            success = XPBlock.delete().where(
                (XPBlock.guild_id == event.guild.id) &
                (XPBlock.user_id == user.id)
            ).execute()
            
            if not success:
                raise CommandFail('{} was not blocked from gaining XP'.format(
                    user,
                ))
        else:
            raise CommandFail('Invalid user')

        raise CommandSuccess('Unblocked {} from gaining XP.'.format(member))

    @Plugin.command('xp', '[user:user|snowflake]')
    def xp(self, event, user=None):
        member = user if user else event.author

        try:
            gml = GuildMemberLevel.select().where(
                (GuildMemberLevel.user_id == member.id) &
                (GuildMemberLevel.guild_id == event.guild.id)
            ).get()
        except GuildMemberLevel.DoesNotExist:
            raise CommandFail('That user does not have any XP (Have they sent a message?)')

        raise CommandSuccess('{} is level {} ({} XP)'.format(member, self.level_from_xp(gml.xp), gml.xp))

    @Plugin.command('leaderboard', '[places:int] [offset:int]', group='xp', aliases=['top'])
    def xp_leaderboard(self, event, places=None, offset=None):
        places = places if places else 10
        offset = offset if offset else 0
        user = User.alias()

        leaderboard = GuildMemberLevel.select(GuildMemberLevel, user).join(
            user,
            on=((GuildMemberLevel.user_id == user.user_id).alias('user'))
        ).where(
            GuildMemberLevel.guild_id == event.guild.id,
            GuildMemberLevel.xp > 0
        ).order_by(GuildMemberLevel.xp.desc()).offset(offset).limit(places)

        tbl = MessageTable()
        tbl.set_header('Place', 'User', 'Level (XP)')
        for place, entry in enumerate(leaderboard, start=(offset if offset else 1)):
            tbl.add(
                place,
                str(entry.user),
                '{} ({})'.format(self.level_from_xp(entry.xp), entry.xp)
            )
    
        event.msg.reply(tbl.compile())

    @Plugin.command('reset', '<user:user|snowflake>',
    #aliases=[],
    context={'action': 'reset'},
    group='xp',
    level=CommandLevels.ADMIN)
    @Plugin.command('give', '<user:user|snowflake> <amount:int>',
    aliases=['add'],
    context={'action': 'give'},
    group='xp', 
    level=CommandLevels.ADMIN)
    @Plugin.command('take', '<user:user|snowflake> <amount:int>',
    aliases=['remove'],
    context={'action': 'take'},
    group='xp',
    level=CommandLevels.ADMIN)
    def xp_edit(self, event, user, amount=None, action=None):
        member = event.guild.get_member(user)

        if not member:
            raise CommandFail('Invalid member')

        if not isinstance(amount, int) and action != "reset":
            raise CommandFail('Invalid amount')

        # self.can_act_on(event, member.id)

        if action == 'give':
            try:
                user = GuildMemberLevel.select().where(
                    (GuildMemberLevel.user_id == member.id) &
                    (GuildMemberLevel.guild_id == member.guild_id)
                ).get()
            except GuildMemberLevel.DoesNotExist:
                user = GuildMemberLevel.create_new(member)

            user.add_xp(member.guild_id, member.id, amount)

            raise CommandSuccess('{} is now Level {} ({} XP)'.format(
                member.user,
                self.level_from_xp(user.xp + amount),
                (user.xp + amount)
            ))
        elif action == 'take':
            try:
                user = GuildMemberLevel.select().where(
                    (GuildMemberLevel.user_id == member.id) &
                    (GuildMemberLevel.guild_id == member.guild_id)
                ).get()
            except GuildMemberLevel.DoesNotExist:
                user = GuildMemberLevel.create_new(member)
                event.channel.send_message('You\'re a monster. Negative XP?')

            user.rmv_xp(member.guild_id, member.id, amount)

            raise CommandSuccess('{} is now Level {} ({} XP)'.format(
                member.user,
                self.level_from_xp(user.xp - amount),
                (user.xp - amount)
            ))
        else:
            try:
                user = GuildMemberLevel.select().where(
                    (GuildMemberLevel.user_id == member.id) &
                    (GuildMemberLevel.guild_id == member.guild_id)
                ).get()
            except GuildMemberLevel.DoesNotExist:
                raise CommandFail('This user cannot be reset.')

            msg = event.msg.reply('Really reset `{}`?'.format(member))

            msg.chain(False).\
                add_reaction(GREEN_TICK_EMOJI).\
                add_reaction(RED_TICK_EMOJI)

            try:
                mra_event = self.wait_for_event(
                    'MessageReactionAdd',
                    message_id=msg.id,
                    conditional=lambda e: (
                        e.emoji.id in (GREEN_TICK_EMOJI_ID, RED_TICK_EMOJI_ID) and
                        e.user_id == event.author.id
                    )).get(timeout=10)
            except gevent.Timeout:
                return
            finally:
                msg.delete()

            if mra_event.emoji.id != GREEN_TICK_EMOJI_ID:
                return

            user.reset_member(event.guild.id, member.id)
            raise CommandSuccess('{} has been reset.'.format(member))

        # TODO: Modlog call :)

