from disco.bot import CommandLevels
from disco.util.sanitize import S
from disco.types.message import MessageEmbed

from rowboat.plugins import RowboatPlugin as Plugin, CommandFail, CommandSuccess
from rowboat.types import Field
from rowboat.types.plugin import PluginConfig
from rowboat.models.tags import Tag
from rowboat.models.user import User, XPBlock
from rowboat.models.guild import GuildMemberLevel

class LevelConfig(PluginConfig):
    pass

@Plugin.with_config(LevelConfig)
class LevelPlugin(Plugin):

    #TODO: Do message event stuff lulw

    def can_act_on(self, event, victim_id, throw=True):
        if event.author.id == victim_id:
            if not throw:
                return False
            raise CommandFail('Cannot execute that action on yourself')
    
    #confirmed
    @Plugin.command('block', '<user:user|snowflake> [reason:str...]', group='xp2', aliases=['mute', 'stfu'], level=CommandLevels.MOD)
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
            user = GuildMemberLevel.get().where(
                (GuildMemberLevel.user_id == member.id) &
                (GuildMemberLevel.guild_id == member.guild_id)
            ).execute()
        except:
            raise CommandFail('No level data, have they sent a message?')

        if action == 'give':
            user.add_xp(amount)

            raise CommandSuccess('{} was given {} XP. (New Total: `{}`)'.format(
                member.alias,
                amount,
                'in dev' #Get Current Amount (do above and just pull as var w/ this amt+ added)
            ))
        elif action == 'take':
            user.rmv_xp(amount)

            raise CommandSuccess('Took {} XP from {}. (New Total: `{}`)'.format(
                amount,
                member.alias,
                'in dev'
                #Get Current Amount (do above and just pull as var w/ this amt+ added)
            ))
        else:
            raise CommandSuccess('not done')
	    #Reset to 0
            #Do the gevent confirm action

        #TODO: Modlog call :)

