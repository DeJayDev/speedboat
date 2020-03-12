from disco.bot import CommandLevels
from disco.util.sanitize import S
from disco.types.message import MessageEmbed

from rowboat.plugins import RowboatPlugin as Plugin, CommandFail, CommandSuccess
from rowboat.types import Field
from rowboat.types.plugin import PluginConfig
from rowboat.models.tags import Tag
from rowboat.models.user import User, XPBlock
from rowboat.models.guild import GuildMemberLevel
from rowboat.constants import (
    GREEN_TICK_EMOJI_ID, RED_TICK_EMOJI_ID, GREEN_TICK_EMOJI, RED_TICK_EMOJI
)

import math

class LevelConfig(PluginConfig):
    pass

@Plugin.with_config(LevelConfig)
class LevelPlugin(Plugin):

    """
        xp=(225*level)^2
        level=sqrt(xp)/225
        Where y is XP and x is Level
    """

    def xp_to_level(xp):
        return int((math.sqrt(xp)/225))

    def unload(self, ctx):
        super(LevelPlugin, self).unload(ctx)

    @Plugin.listen('MessageCreate')
    def on_message_create(self, event):
        user = None
        if event.author.bot:
            return
        
        guild = self.call('CorePlugin.get_guild', event.guild.id)
        config = guild and guild.get_config()

        commands = list(self.bot.get_commands_for_message(
            config.commands.mention,
            {},
            config.commands.prefix,
            event.message))

        if len(commands) > 1:
            return

        try: 
            user = GuildMemberLevel.select().where(
                (GuildMemberLevel.user_id == event.author.id) &
                (GuildMemberLevel.guild_id == event.guild.id)
            ).get()

            blocked = XPBlock.get_or_none(
                (XPBlock.user_id == event.author.id) &
                (XPBlock.guild_id == event.guild.id)
            )

            if blocked is None:
                user.add_xp(1)
        
        except GuildMemberLevel.DoesNotExist:
            GuildMemberLevel.create(
                user_id = event.author.id,
                guild_id = event.guild.id,
                xp = 0
            )

    def can_act_on(self, event, victim_id, throw=True):
        if event.author.id == victim_id:
            if not throw:
                return False
            raise CommandFail('Cannot execute that action on yourself')
    
    #confirmed
    @Plugin.command('block', '<user:user|snowflake> <reason:str...>', group='xp2', aliases=['mute', 'stfu'], level=CommandLevels.MOD)
    def xp_block(self, event, user, reason):
        member = event.guild.get_member(user)
        if member:
            self.can_act_on(event, member.id)
            _, created = XPBlock.get_or_create(
                guild_id = event.guild.id,
                user_id = user.id,
                defaults={
                    'actor_id': event.author.id,
                    'reason': reason
                })
            
            if not created:
                raise CommandFail('{} is already blocked from gaining XP'.format(
                    user,
                ))
        else:
            raise CommandFail('Invalid user')

        raise CommandSuccess('Blocked {} from gaining XP.'.format(member))

    #confirmed
    @Plugin.command('unblock', '<user:user|snowflake> [reason:str...]', group='xp2', aliases=['unmute'], level=CommandLevels.MOD)
    def xp_unblock(self, event, user, reason=None):
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

    @Plugin.command('xp', '[target:user|snowflake]')
    def xp_view(self, event, target=None):
        if target is None:
            target = event.author

        user = None
        try: 
            user = GuildMemberLevel.select().where(
                (GuildMemberLevel.user_id == target.id) &
                (GuildMemberLevel.guild_id == event.guild.id)
            ).get()
            raise CommandSuccess('{} is Level {} ({} XP)'.format(
                target, 
                '??',
                user.xp))
        except GuildMemberLevel.DoesNotExist:
            raise CommandFail('No level data, have they sent a message?')
        
    
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

        if amount is not None and not isinstance(amount, int):
            raise CommandFail('Invalid amount')

        self.can_act_on(event, member.id)

        user = None

        try: 
            user = GuildMemberLevel.select().where(
                (GuildMemberLevel.user_id == member.id) &
                (GuildMemberLevel.guild_id == member.guild_id)
            ).get()
        except:
            raise CommandFail('No level data, have they sent a message?')

        if action == 'give':
            user.add_xp(amount)

            raise CommandSuccess('Gave {} {} XP (New Total: {})'.format(
                member,
                amount,
                user.xp #Get Current Amount (do above and just pull as var w/ this amt+ added)
            ))
        elif action == 'take':
            user.rmv_xp(amount)

            raise CommandSuccess('Removed {} XP from {} (New Total: {})'.format(
                amount,
                member,
                user.xp
                #Get Current Amount (do above and just pull as var w/ this amt+ added)
            ))
        else:
            """here"""
            msg = event.msg.reply(
                'Please confirm you\'d like to remove {} XP from {}'.format(
                    user.xp,
                    member
                ))
                
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
                msg.reply('Not resetting user.')
                msg.delete()
                return

            msg.delete()

            if mra_event.emoji.id == GREEN_TICK_EMOJI_ID:
                msg = msg.reply('Resetting user...')
                user.reset_member(event.guild.id, member.id)
                msg.edit('Ok, reset user.')
            else:
                msg = msg.reply('Not resetting user.')

        #TODO: Modlog call :)
