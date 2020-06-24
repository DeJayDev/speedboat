import gevent

from random import randint

from disco.bot import CommandLevels
from disco.util.sanitize import S
from disco.types.message import MessageEmbed, MessageTable

from rowboat.plugins import RowboatPlugin as Plugin, CommandFail, CommandSuccess
from rowboat.types import Field
from rowboat.types.plugin import PluginConfig
from rowboat.models.tags import Tag
from rowboat.models.user import User, XPBlock
from rowboat.models.guild import GuildMemberLevel

from rowboat.constants import (
    GREEN_TICK_EMOJI_ID, RED_TICK_EMOJI_ID, GREEN_TICK_EMOJI, RED_TICK_EMOJI
)

class LevelPluginConfig(PluginConfig):
    pass

@Plugin.with_config(LevelPluginConfig)
class LevelPlugin(Plugin):

    def can_act_on(self, event, victim_id, throw=True):
        if event.author.id == victim_id:
            if not throw:
                return False
            raise CommandFail('Cannot execute that action on yourself')
    
    def level_from_exp(self, exp):
        def getLevelExp(level):
            return (5*(level**2)+50*level+100)

        level = 0;

        while exp >= getLevelExp(level):
            exp -= getLevelExp(level)
            level += 1

        return level

    @Plugin.listen('MessageCreate')
    def xp_message_send(self, event):
        if event.author.bot or (event.author.discriminator == '0000'):
            return

        config = self.call('CorePlugin.get_config', event.guild.id)

        if config and config.commands:
            commands = list(self.bot.get_commands_for_message(
                config.commands.mention,
                {},
                config.commands.prefix,
                event.message))
        
        if commands:
            return # No XP for commands

        try:
            user = GuildMemberLevel.select(GuildMemberLevel, XPBlock).join(
                XPBlock,
                on=((GuildMemberLevel.guild_id == XPBlock.guild_id) &
                    (GuildMemberLevel.user_id == XPBlock.user_id))
            ).where(
                (GuildMemberLevel.user_id == event.author.id) &
                (GuildMemberLevel.guild_id == event.guild.id)
            ).get()

            if user.xpblock:
                return # No XP for blocked meanies >:(
        except GuildMemberLevel.DoesNotExist:
            user = GuildMemberLevel.create_new(event.guild.get_member(event.author.id)) # lol

        user.add_xp(event.guild.id, event.author.id, randint(15, 25))
    
    @Plugin.command('block', '<user:user|snowflake> [reason:str...]', group='xp2', aliases=['mute', 'stfu'], level=CommandLevels.MOD)
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

    @Plugin.command('unblock', '<user:user|snowflake>', group='xp2', aliases=['unmute'], level=CommandLevels.MOD)
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

    @Plugin.command('xp2', '[user:user|snowflake]')
    def xp(self, event, user=None):
        member = user if user else event.author

        try:
            gml = GuildMemberLevel.select().where(
                (GuildMemberLevel.user_id == member.id) &
                (GuildMemberLevel.guild_id == event.guild.id)
            ).get()
        except GuildMemberLevel.DoesNotExist:
            raise CommandFail('That user does not have any XP (Have they sent a message?)')

        raise CommandSuccess('{} is level {} ({} XP)'.format(member, self.level_from_exp(gml.xp), gml.xp))

    @Plugin.command('leaderboard', '[places:int] [offset:int]', group='xp2', aliases=['top'])
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
                '{} ({})'.format(self.level_from_exp(entry.xp), entry.xp)
            )
    
        event.msg.reply(tbl.compile())

    @Plugin.command('reset', '<user:user|snowflake>',
    #aliases=[],
    context={'action': 'reset'},
    group='xp2',
    level=CommandLevels.ADMIN)
    @Plugin.command('give', '<user:user|snowflake> <amount:int>',
    aliases=['add'],
    context={'action': 'give'},
    group='xp2', 
    level=CommandLevels.ADMIN)
    @Plugin.command('take', '<user:user|snowflake> <amount:int>',
    aliases=['remove'],
    context={'action': 'take'},
    group='xp2',
    level=CommandLevels.ADMIN)
    def xp_edit(self, event, user, amount=None, action=None):
        member = event.guild.get_member(user)

        if not member:
            raise CommandFail('Invalid member')

        if not isinstance(amount, int) and action != "reset":
            raise CommandFail('Invalid amount')

        #self.can_act_on(event, member.id)

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
                self.level_from_exp(user.xp + amount),
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
                self.level_from_exp(user.xp - amount),
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

        #TODO: Modlog call :)

