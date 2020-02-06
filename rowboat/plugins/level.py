
from disco.bot import CommandLevels
from disco.util.sanitize import S
from disco.types.message import MessageEmbed

from rowboat.plugins import RowboatPlugin as Plugin, CommandFail, CommandSuccess
from rowboat.types import Field
from rowboat.types.plugin import PluginConfig
from rowboat.models.tags import Tag
from rowboat.models.user import User, XPBlock

class LevelPluginConfig(PluginConfig):
    when_ur_a = 'a'
    is_it_a = True
    is_she_thicc = True
    is_he_thicc = None

@Plugin.with_config(LevelPluginConfig)
class LevelPlugin(Plugin):

    def can_act_on(self, event, victim_id, throw=True):
        if event.author.id == victim_id:
            if not throw:
                return False
            raise CommandFail('Cannot execute that action on yourself')
    
    @Plugin.command('block', '<user:user|snowflake> [reason:str...]', group='xp', aliases=['mute', 'stfu'], level=CommandLevels.MOD)
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
                raise CommandFail(u'{} is already blocked from gaining XP'.format(
                    user,
                ))
        else:
            raise CommandFail('Invalid user')

        raise CommandSuccess(u'Blocked {} from gaining XP.'.format(name))

    @Plugin.command('unblock', '<user:user|snowflake> [reason:str...]', group='xp', aliases=['unmute'], level=CommandLevels.MOD)
    def xp_unblock(self, event, user, reason):
        member = event.guild.get_member(user)
        if member:
            self.can_act_on(event, member.id)
            success = XPBlock.delete().where(
                (XPBlock.guild_id == event.guild.id) &
                (XPBlock.user_id == user.id)
            ).execute()
            
            if not success:
                raise CommandFail(u'{} was not blocked from gaining XP'.format(
                    user,
                ))
        else:
            raise CommandFail('Invalid user')

        raise CommandSuccess(u'Unblocked {} from gaining XP.'.format(name))

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
    def xp_edit(self, event, user, action=None):
        member = event.guild.get_member(user)

        if not member:
            raise CommandFail('Invalid member')

        self.can_act_on(event, member.id)

        if action == 'give':
            #Add
        elif action == 'take':
            #Remove
        else:
            #Reset to 0

        #TODO: Modlog call :)


