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

@Plugin.with_config(MediaConfig)
class MediaPlugin(Plugin):

    def wait_for_stream(self):
        ps = rdb.pubsub()
        ps.subscribe('media')

        for item in ps.listen():
            if item['type'] != 'message':
                continue
            
            data = json.loads(item['data'])

            self.state.channels[686962489820315689].send_message(data)
            
            #TODO: if offline, send the object
            # else format the embed and find out where it goes

    @Plugin.command('streams', aliases=['media'], level=-1)
    def streams_list(self, event):
        #Use the MessageTable, it'll be cute
        raise CommandSuccess('indev.')

    @Plugin.command('add', '<streamer:str...>' aliases=['follow'], level=CommandLevels.ADMIN)
    def streams_add(self, event, streamer):
        raise CommandSuccess('ok')