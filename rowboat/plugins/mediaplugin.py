from disco.bot import CommandLevels
from disco.util.sanitize import S
from disco.types.message import MessageEmbed

from rowboat.plugins import RowboatPlugin as Plugin, CommandFail, CommandSuccess
from rowboat.types import Field
from rowboat.types.plugin import PluginConfig
from rowboat.redis import rdb
from rowboat.models.tags import Tag
from rowboat.models.user import User
from rowboat.models.guild import GuildStreamSubscriptions

class MediaConfig(PluginConfig):
    pass
#    when_ur_a = 'a'
#    is_it_a = True
#    is_she_thicc = True
#    is_he_thicc = None

@Plugin.with_config(MediaConfig)
class MediaPlugin(Plugin):

    def wait_for_stream(self):
        ps = rdb.pubsub()
        ps.subscribe('media')

        for item in ps.listen():
            if item['type'] != 'message':
                continue
            
            data = json.loads(item['data'])
            
            #TODO: if offline, send the object
            # else format the embed and find out where it goes

    @Plugin.command('streams', aliases=['media'], level=-1)
    def xp_block(self, event, user):
        raise CommandSuccess('Blocked {} from gaining XP.'.format(member))
