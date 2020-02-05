import os
import json
import pprint
import signal
import inspect
import humanize
import functools
import contextlib
import time

from datetime import datetime, timedelta
from holster.emitter import Priority, Emitter
from disco.bot import Bot
from disco.types.message import MessageEmbed
from disco.types.permissions import Permissions
from disco.api.http import APIException
from disco.bot.command import CommandEvent
from disco.util.sanitize import S
from disco.util.snowflake import to_datetime

from rowboat import ENV
from rowboat.util import LocalProxy
from rowboat.util.stats import timed
from rowboat.plugins import RowboatPlugin as Plugin, CommandFail, CommandSuccess, CommandResponse
from rowboat.sql import init_db
from rowboat.redis import rdb

import rowboat.models
from rowboat.models.user import Infraction
from rowboat.models.guild import Guild, GuildBan
from rowboat.models.message import Command
from rowboat.models.notification import Notification
from rowboat.plugins.modlog import Actions
from rowboat.constants import (
    GREEN_TICK_EMOJI, RED_TICK_EMOJI, ROWBOAT_GUILD_ID, ROWBOAT_USER_ROLE_ID,
    ROWBOAT_CONTROL_CHANNEL
)

PY_CODE_BLOCK = u'```py\n{}\n```'

BOT_INFO = '''
Speedboat is a modernized fork of rowboat, a moderation and utilitarian bot built for large Discord servers.
'''

GUILDS_WAITING_SETUP_KEY = 'gws'

class CorePlugin(Plugin):
    def load(self, ctx):
        init_db(ENV)

        self.startup = ctx.get('startup', datetime.utcnow())
        self.guilds = ctx.get('guilds', {})

        self.emitter = Emitter()

        super(CorePlugin, self).load(ctx)

        # Overwrite the main bot instances plugin loader so we can magicfy events
        self.bot.add_plugin = self.our_add_plugin

        if ENV != 'prod':
            self.spawn(self.wait_for_plugin_changes)

        self._wait_for_actions_greenlet = self.spawn(self.wait_for_actions)

    def spawn_wait_for_actions(self, *args, **kwargs):
        self._wait_for_actions_greenlet = self.spawn(self.wait_for_actions)
        self._wait_for_actions_greenlet.link_exception(self.spawn_wait_for_actions)

    def our_add_plugin(self, cls, *args, **kwargs):
        if getattr(cls, 'global_plugin', False):
            Bot.add_plugin(self.bot, cls, *args, **kwargs)
            return

        inst = cls(self.bot, None)
        inst.register_trigger('command', 'pre', functools.partial(self.on_pre, inst))
        inst.register_trigger('listener', 'pre', functools.partial(self.on_pre, inst))
        Bot.add_plugin(self.bot, inst, *args, **kwargs)

    def wait_for_plugin_changes(self):
        import gevent_inotifyx as inotify

        fd = inotify.init()
        inotify.add_watch(fd, 'rowboat/plugins/', inotify.IN_MODIFY)
        while True:
            events = inotify.get_events(fd)
            for event in events:
                # Can't reload core.py sadly
                if event.name.startswith('core.py'):
                    continue

                plugin_name = '{}Plugin'.format(event.name.split('.', 1)[0].title())
                plugin = next((v for k, v in self.bot.plugins.items() if k.lower() == plugin_name.lower()), None)
                if plugin:
                    self.log.info('Detected change in %s, reloading...', plugin_name)
                    try:
                        plugin.reload()
                    except Exception:
                        self.log.exception('Failed to reload: ')

    def wait_for_actions(self):
        ps = rdb.pubsub()
        ps.subscribe('actions')

        for item in ps.listen():
            if item['type'] != 'message':
                continue

            data = json.loads(item['data'])
            if data['type'] == 'GUILD_UPDATE' and data['id'] in self.guilds:
                with self.send_control_message() as embed:
                    embed.title = u'Reloaded config for {}'.format(
                        self.guilds[data['id']].name
                    )

                self.log.info(u'Reloading guild %s', self.guilds[data['id']].name)

                # Refresh config, mostly to validate
                try:
                    config = self.guilds[data['id']].get_config(refresh=True)

                    # Reload the guild entirely
                    self.guilds[data['id']] = Guild.with_id(data['id'])

                    # Update guild access
                    self.update_rowboat_guild_access()

                    # Finally, emit the event
                    self.emitter.emit('GUILD_CONFIG_UPDATE', self.guilds[data['id']], config)
                except:
                    self.log.exception(u'Failed to reload config for guild %s', self.guilds[data['id']].name)
                    continue
            elif data['type'] == 'RESTART':
                self.log.info('Restart requested, signaling parent')
                os.kill(os.getppid(), signal.SIGUSR1)

    def unload(self, ctx):
        ctx['guilds'] = self.guilds
        ctx['startup'] = self.startup
        super(CorePlugin, self).unload(ctx)

    def update_rowboat_guild_access(self):
#        if ROWBOAT_GUILD_ID not in self.state.guilds or ENV != 'prod':
#            return

        rb_guild = self.state.guilds.get(ROWBOAT_GUILD_ID)
        if not rb_guild:
            return

        self.log.info('Updating speedboat guild access')

        guilds = Guild.select(
            Guild.guild_id,
            Guild.config
        ).where(
            (Guild.enabled == 1)
        )

        users_who_should_have_access = set()
        for guild in guilds:
            if 'web' not in guild.config:
                continue

            for user_id in guild.config['web'].keys():
                try:
                    users_who_should_have_access.add(int(user_id))
                except:
                    self.log.warning('Guild %s has invalid user ACLs: %s', guild.guild_id, guild.config['web'])

        # TODO: sharding
        users_who_have_access = {
            i.id for i in rb_guild.members.values()
            if ROWBOAT_USER_ROLE_ID in i.roles
        }

        remove_access = set(users_who_have_access) - set(users_who_should_have_access)
        add_access = set(users_who_should_have_access) - set(users_who_have_access)

        for user_id in remove_access:
            member = rb_guild.members.get(user_id)
            if not member:
                continue

            member.remove_role(ROWBOAT_USER_ROLE_ID)

        for user_id in add_access:
            member = rb_guild.members.get(user_id)
            if not member:
                continue

            member.add_role(ROWBOAT_USER_ROLE_ID)

    def on_pre(self, plugin, func, event, args, kwargs):
        """
        This function handles dynamically dispatching and modifying events based
        on a specific guilds configuration. It is called before any handler of
        either commands or listeners.
        """
        if hasattr(event, 'guild') and event.guild:
            guild_id = event.guild.id
        elif hasattr(event, 'guild_id') and event.guild_id:
            guild_id = event.guild_id
        else:
            guild_id = None

        if guild_id not in self.guilds:
            if isinstance(event, CommandEvent):
                if event.command.metadata.get('global_', False):
                    return event
            elif hasattr(func, 'subscriptions'):
                if func.subscriptions[0].metadata.get('global_', False):
                    return event

            return

        if hasattr(plugin, 'WHITELIST_FLAG'):
            if not int(plugin.WHITELIST_FLAG) in self.guilds[guild_id].whitelist:
                return

        event.base_config = self.guilds[guild_id].get_config()
        if not event.base_config:
            return

        plugin_name = plugin.name.lower().replace('plugin', '')
        if not getattr(event.base_config.plugins, plugin_name, None):
            return

        self._attach_local_event_data(event, plugin_name, guild_id)

        return event

    def get_config(self, guild_id, *args, **kwargs):
        # Externally Used
        return self.guilds[guild_id].get_config(*args, **kwargs)

    def get_guild(self, guild_id):
        # Externally Used
        return self.guilds[guild_id]

    def _attach_local_event_data(self, event, plugin_name, guild_id):
        if not hasattr(event, 'config'):
            event.config = LocalProxy()

        if not hasattr(event, 'rowboat_guild'):
            event.rowboat_guild = LocalProxy()

        event.config.set(getattr(event.base_config.plugins, plugin_name))
        event.rowboat_guild.set(self.guilds[guild_id])

    @Plugin.schedule(290, init=False)
    def update_guild_bans(self):
        to_update = [
            guild for guild in Guild.select().where(
                (Guild.last_ban_sync < (datetime.utcnow() - timedelta(days=1))) |
                (Guild.last_ban_sync >> None)
            )
            if guild.guild_id in self.client.state.guilds]

        # Update 10 at a time
        for guild in to_update[:10]:
            guild.sync_bans(self.client.state.guilds.get(guild.guild_id))

    @Plugin.listen('GuildUpdate')
    def on_guild_update(self, event):
        self.log.info('Got guild update for guild %s (%s)', event.guild.id, event.guild.channels)

    @Plugin.listen('GuildBanAdd')
    def on_guild_ban_add(self, event):
        GuildBan.ensure(self.client.state.guilds.get(event.guild_id), event.user)

    @Plugin.listen('GuildBanRemove')
    def on_guild_ban_remove(self, event):
        GuildBan.delete().where(
            (GuildBan.user_id == event.user.id) &
            (GuildBan.guild_id == event.guild_id)
        )

    @contextlib.contextmanager
    def send_control_message(self):
        embed = MessageEmbed()
        embed.set_footer(text='Speedboat {}'.format(
            'Production' if ENV == 'prod' else 'Testing'
        ))
        embed.timestamp = datetime.utcnow().isoformat()
        embed.color = 0x779ecb
        try:
            yield embed
            self.bot.client.api.channels_messages_create(
                ROWBOAT_CONTROL_CHANNEL,
                embed=embed
            )
        except:
            self.log.exception('Failed to send control message:')
            return

    @Plugin.listen('Resumed')
    def on_resumed(self, event):
        Notification.dispatch(
            Notification.Types.RESUME,
            env=ENV,
        )

        with self.send_control_message() as embed:
            embed.title = 'Resumed'
            embed.color = 0xffb347
            embed.add_field(name='Replayed Events', value=str(self.client.gw.replayed_events))

    @Plugin.listen('Ready', priority=Priority.BEFORE)
    def on_ready(self, event):
        reconnects = self.client.gw.reconnects
        self.log.info('Started session %s', event.session_id)
        Notification.dispatch(
            Notification.Types.CONNECT,
            env=ENV,
        )

        with self.send_control_message() as embed:
            if reconnects:
                embed.title = 'Reconnected'
                embed.color = 0xffb347
            else:
                embed.title = 'Connected'
                embed.color = 0x77dd77

    @Plugin.listen('GuildCreate', priority=Priority.BEFORE, conditional=lambda e: not e.created)
    def on_guild_create(self, event):
        try:
            guild = Guild.with_id(event.id)
        except Guild.DoesNotExist:
            # If the guild is not awaiting setup, leave it now
            if not rdb.sismember(GUILDS_WAITING_SETUP_KEY, str(event.id)) and event.id != ROWBOAT_GUILD_ID:
                self.log.warning(
                    'I am in guild %s (%s), and it\'s not within the  setup list',
                    event.id, event.name
                )
                #event.guild.leave()
            return

        if not guild.enabled:
            return

        config = guild.get_config()
        if not config:
            return

        # Ensure we're updated
        self.log.info('Requesting Guild: %s (%s)', event.guild.name, event.guild.id)
        guild.sync(event.guild)
        
#        guild.request_guild_members()

        self.guilds[event.id] = guild

        if config.nickname:
            def set_nickname():
                m = event.members.select_one(id=self.state.me.id)
                if m and m.nick != config.nickname:
                    try:
                        m.set_nickname(config.nickname)
                    except APIException as e:
                        self.log.warning('Failed to set nickname for guild %s (%s)', event.guild, e.content)
            self.spawn_later(5, set_nickname)

    def get_level(self, guild, user):
        config = (guild.id in self.guilds and self.guilds.get(guild.id).get_config())

        user_level = 0
        if config:
            member = guild.get_member(user)
            if not member:
                return user_level

            for oid in member.roles:
                if oid in config.levels and config.levels[oid] > user_level:
                    user_level = config.levels[oid]

            # User ID overrides should override all others
            if member.id in config.levels:
                user_level = config.levels[member.id]

        return user_level

    @Plugin.listen('MessageCreate')
    def on_message_create(self, event):
        """
        This monstrosity of a function handles the parsing and dispatching of
        commands.
        """
        # Ignore messages sent by bots
        # TODO: Add command to add channel to ignored_channels
        if event.message.author.bot or rdb.sismember('ignored_channels', event.message.channel_id):
            return
        if not event.channel.type == 1:
            if not event.message.channel.get_permissions(self.state.me).can(Permissions.SEND_MESSAGES):
                return

        # If this is message for a guild, grab the guild object
        if hasattr(event, 'guild') and event.guild:
            guild_id = event.guild.id
        elif hasattr(event, 'guild_id') and event.guild_id:
            guild_id = event.guild_id
        else:
            guild_id = None

        guild = self.guilds.get(event.guild.id) if guild_id else None
        config = guild and guild.get_config()

        # If the guild has configuration, use that (otherwise use defaults)
        if config and config.commands:
            commands = list(self.bot.get_commands_for_message(
                config.commands.mention,
                {},
                config.commands.prefix,
                event.message))
        elif guild_id:
            # Otherwise, default to requiring mentions
            commands = list(self.bot.get_commands_for_message(True, {}, '', event.message))
        else:
            if ENV != 'prod':
                if not event.message.content.startswith(ENV + '!'):
                    return
                event.message.content = event.message.content[len(ENV) + 1:]

            # DM's just use the commands (no prefix/mention)
            commands = list(self.bot.get_commands_for_message(False, {}, '', event.message))

        # If we didn't find any matching commands, return
        if not len(commands):
            return

        event.user_level = self.get_level(event.guild, event.author) if event.guild else 0

        # Grab whether this user is a global admin
        # TODO: cache this
        global_admin = rdb.sismember('global_admins', event.author.id)

        # Iterate over commands and find a match
        for command, match in commands:
            if command.level == -1 and not global_admin:
                continue

            level = command.level

            if guild and not config and command.triggers[0] != 'setup':
                continue
            elif config and config.commands and command.plugin != self:
                overrides = {}
                for obj in config.commands.get_command_override(command):
                    overrides.update(obj)

                if overrides.get('disabled'):
                    continue

                level = overrides.get('level', level)

            if not global_admin and event.user_level < level:
                continue

            with timed('rowboat.command.duration', tags={'plugin': command.plugin.name, 'command': command.name}):
                try:
                    command_event = CommandEvent(command, event.message, match)
                    command_event.user_level = event.user_level
                    command.plugin.execute(command_event)
                except CommandResponse as e:
                    event.reply(e.response)
                except:
                    tracked = Command.track(event, command, exception=True)
                    self.log.exception('Command Error:')

                    with self.send_control_message() as embed:
                        embed.title = u'Command Error: {}'.format(command.name)
                        embed.color = 0xff6961
                        embed.add_field(
                            name='Author', value=u'({}) `{}`'.format(event.author, event.author.id), inline=True)
                        embed.add_field(name='Channel', value='({}) `{}`'.format(
                            event.channel.name,
                            event.channel.id
                        ), inline=True)
                        embed.description = '```{}```'.format(u'\n'.join(tracked.traceback.split('\n')[-8:]))

                    return event.reply('<:{}> something went wrong, perhaps try again later'.format(RED_TICK_EMOJI))

            Command.track(event, command)

            # Dispatch the command used modlog event
            if config:
                modlog_config = getattr(config.plugins, 'modlog', None)
                if not modlog_config:
                    return

                self._attach_local_event_data(event, 'modlog', event.guild.id)

                plugin = self.bot.plugins.get('ModLogPlugin')
                if plugin:
                    plugin.log_action(Actions.COMMAND_USED, event)

            return

    @Plugin.command('setup')
    def command_setup(self, event):
        if not event.guild:
            raise CommandFail('This command can only be used in servers')

        global_admin = rdb.sismember('global_admins', event.author.id)

        # Make sure this is the owner of the server
        if not global_admin:
            if not event.guild.owner_id == event.author.id:
                raise CommandFail('Only the server owner can setup speedboat')

        # Make sure we have admin perms
        m = event.guild.members.select_one(id=self.state.me.id)
        if not m.permissions.administrator and not global_admin:
            raise CommandFail('Bot must have the Administrator permission')

        guild = Guild.setup(event.guild)
        rdb.srem(GUILDS_WAITING_SETUP_KEY, str(event.guild.id))
        self.guilds[event.guild.id] = guild
        raise CommandSuccess('Successfully loaded configuration')

    @Plugin.command('nuke', '<user:snowflake> <reason:str...>', level=-1)
    def nuke(self, event, user, reason):
        contents = []

        for gid, guild in self.guilds.items():
            guild = self.state.guilds[gid]
            perms = guild.get_permissions(self.state.me)

            if not perms.ban_members and not perms.administrator:
                contents.append(u':x: {} - Could not Ban'.format(
                    guild.name
                ))
                continue

            try:
                Infraction.ban(
                    self.bot.plugins.get('AdminPlugin'),
                    event,
                    user,
                    reason,
                    guild=guild)
            except:
                contents.append(u':x: {} - Error'.format(
                    guild.name
                ))
                self.log.exception('Failed to force ban %s in %s', user, gid)

            contents.append(u':white_check_mark: {} - :regional_indicator_f:'.format(
                guild.name
            ))

        event.msg.reply('The Damage:\n' + '\n'.join(contents))

    @Plugin.command('unnuke', '<user:snowflake> <reason:str...>', level=-1)
    def unnuke(self, event, user, reason):
        contents = []

        for gid, guild in self.guilds.items():
            guild = self.state.guilds[gid]
            perms = guild.get_permissions(self.state.me)

            if not perms.ban_members and not perms.administrator:
                contents.append(u':x: {} - Could not Unban'.format(
                    guild.name
                ))
                continue

            try:
                Infraction.create(
                    guild_id=guild.id,
                    user_id=user,
                    actor_id=self.client.api.users_me_get().id,
                    type_=Infraction.Types.UNBAN,
                    reason=reason
                )

                GuildBan.get(user_id=user, guild_id=guild.id)
                guild.delete_ban(user)
            except:
                contents.append(u':x: {} - Error'.format(
                    guild.name
                ))
                self.log.exception('Failed to remove ban for %s in %s', user, gid)

            contents.append(u':white_check_mark: {} - Fixed :heart:'.format(
                guild.name
            ))

        event.msg.reply('Result:\n' + '\n'.join(contents))

    @Plugin.command('about')
    def command_about(self, event):
        embed = MessageEmbed()
        embed.set_author(name='Speedboat', icon_url=self.client.state.me.avatar_url, url='https://row.swvn.io/')
        embed.description = BOT_INFO
        embed.add_field(name='Servers', value=str(Guild.select().count()), inline=True)
        embed.add_field(name='Uptime', value=humanize.naturaldelta(datetime.utcnow() - self.startup), inline=True)
        event.msg.reply(embed=embed)

    @Plugin.command('uptime', level=-1)
    def command_uptime(self, event):
        event.msg.reply('Speedboat was started {}'.format(
            humanize.naturaltime(datetime.utcnow() - self.startup)
        ))

    @Plugin.command('source', '<command>', level=-1)
    def command_source(self, event, command=None):
        for cmd in self.bot.commands:
            if command.lower() in cmd.triggers:
                break
        else:
            raise CommandFail(u"Couldn't find command for `{}`".format(S(command, escape_codeblocks=True)))
            return

        code = cmd.func.__code__
        lines, firstlineno = inspect.getsourcelines(code)

        event.msg.reply('<https://github.com/SethBots/speedboat/blob/master/{}#L{}-{}>'.format(
            code.co_filename,
            firstlineno,
            firstlineno + len(lines)
        ))

    @Plugin.command('eval', level=-1)
    def command_eval(self, event):
        ctx = {
            'bot': self.bot,
            'client': self.bot.client,
            'state': self.bot.client.state,
            'event': event,
            'msg': event.msg,
            'guild': event.msg.guild,
            'channel': event.msg.channel,
            'author': event.msg.author
        }

        # Mulitline eval
        src = event.codeblock
        if src.count('\n'):
            lines = filter(bool, src.split('\n'))
            if lines[-1] and 'return' not in lines[-1]:
                lines[-1] = 'return ' + lines[-1]
            lines = '\n'.join('    ' + i for i in lines)
            code = 'def f():\n{}\nx = f()'.format(lines)
            local = {}

            try:
                exec compile(code, '<eval>', 'exec') in ctx, local
            except Exception as e:
                event.msg.reply(PY_CODE_BLOCK.format(type(e).__name__ + ': ' + str(e)))
                return

            result = pprint.pformat(local['x'])
        else:
            try:
                result = str(eval(src, ctx))
            except Exception as e:
                event.msg.reply(PY_CODE_BLOCK.format(type(e).__name__ + ': ' + str(e)))
                return

        if len(result) > 1990:
            event.msg.reply('', attachments=[('result.txt', result)])
        else:
            event.msg.reply(PY_CODE_BLOCK.format(result))

    @Plugin.command('sync-bans', group='control', level=-1)
    def control_sync_bans(self, event):
        guilds = list(Guild.select().where(
            Guild.enabled == 1
        ))

        msg = event.msg.reply(':timer: Pls hold...')

        for guild in guilds:
            guild.sync_bans(self.client.state.guilds.get(guild.guild_id))

        msg.edit('<:{}> synced {} guilds'.format(GREEN_TICK_EMOJI, len(guilds)))

    @Plugin.command('reconnect', group='control', level=-1)
    def control_reconnect(self, event):
        raise CommandSuccess('Closing connection')
        self.client.gw.ws.close()

    @Plugin.command('invite', '<guild:snowflake>', group='guilds', level=-1)
    def guild_join(self, event, guild):
        guild = self.state.guilds.get(guild)
        if not guild:
            return event.msg.reply(':no_entry_sign: invalid or unknown guild ID')

        msg = event.msg.reply(u'Ok, hold on while I get you setup with an invite link to {}'.format(
            guild.name,
        ))

        general_channel = guild.channels[list(guild.channels)[0]]

        try:
            invite = general_channel.create_invite(
                max_age=300,
                max_uses=1,
                unique=True,
            )
        except:
            return msg.edit(u':no_entry_sign: Hmmm, something went wrong creating an invite for {}'.format(
                guild.name,
            ))

        msg.edit(u'Ok, here is a temporary invite for you: discord.gg/{}'.format(
            invite.code,
        ))

    @Plugin.command('wh', '<guild:snowflake>', group='guilds', level=-1)
    def guild_whitelist(self, event, guild):
        rdb.sadd(GUILDS_WAITING_SETUP_KEY, str(guild))
        raise CommandSuccess('Ok, guild %s is now in the whitelist' % guild)

    @Plugin.command('unwh', '<guild:snowflake>', group='guilds', level=-1)
    def guild_unwhitelist(self, event, guild):
        rdb.srem(GUILDS_WAITING_SETUP_KEY, str(guild))
        raise CommandSuccess('Ok, I\'ve made sure guild %s is no longer in the whitelist' % guild)

    @Plugin.command('leave', '<guild:snowflake>', group='guilds', level=-1)
    def guild_leave(self, event, guild):
        guild = self.state.guilds.get(guild)
        guild.leave()
        raise CommandSuccess('Ok, I\'ve left that guild.')

    @Plugin.command('disable', '<plugin:str>', group='plugins', level=-1)
    def plugin_disable(self, event, plugin):
        plugin = self.bot.plugins.get(plugin)
        if not plugin:
            raise CommandFail('It appears that plugin doesn\'t exist')
        self.bot.rmv_plugin(plugin.__class__)
        raise CommandSuccess('Ok, that plugin has been disabled and unloaded')

    @Plugin.command('commands', group='control', level=-1)
    def control_commands(self, event):
        event.msg.reply('__**Punishments**__\n`!mute <mention or ID> [reason]` - Mutes user from talking in text channel (role must be set up).\n`!unmute <mention or ID> [reason]` - Unmutes user.\n`!tempmute <mention or ID> <duration> [reason]` - Temporarily mutes user from talking in text channel for duration.\n`!kick <mention or ID> [reason]` - Kicks user from server.\n`!ban <mention or ID> [reason]` - Bans user, does not delete messages. Must still be in server.\n`!unban <ID> [reason]` - Unbans user. Must use ID.\n`!tempban <mention or ID> <duration> [reason]` - Temporarily bans user for duration.\n`!forceban <ID> <reason>` - Bans user who is not in the server. Must use ID.\n`!softban <mention or ID> [reason]` - Softbans (bans/unbans) user.\n\n__**Admin Utilities**__\n`!clean all <#>` - Deletes # of messages in current channel.\n`!clean bots <#>` - Deletes # of messages sent by bots in current channel.\n`!clean user <mention or ID> <#>` - Deletes # of user\'s messages in current channel. Must use ID if they are no longer in the server.\n`!archive user <mention or ID> [#]` - Creates an archive with all messages found by user.\n`!archive (here / all ) [#]` - Creates an archive with all messages in the server.\n`!archive channel <channel> [#]` - Creates an archive with all messages in the channel.\n`!search <tag or ID>` - Returns some information about the user, ID, time joined, infractions, etc.\n`!role add <mention or ID> <role> [reason]` - Adds the role (either ID or fuzzy-match name) to the user.\n`!role rmv/remove <mention or ID> <role> [reason]` - Removes the role from the user.\n`!r add <duration> <message>` - Adds a reminder to be sent after the specified duration.')
        event.msg.reply('__**Infractions**__\n`!inf search <mention or ID>` - Searches infractions based on the given query.\n`!inf info <inf #>` - Returns information on an infraction.\n`!inf duration <inf #> <duration>` - Updates the duration of an infraction ([temp]ban, [temp]mutes). Duration starts from time of initial action.\n`!reason <inf #> <reason>` - Sets the reason for an infraction.\n\n__**Reactions and Starboard**__\n`!stars <lock | unlock>` - Lock or unlocks the starboard. Locking prevents new posts from being starred.\n`!stars <block | unblock> <mention or ID>` - Blocks or unblocks a user\'s stars from starboard. Their reactions won\'t count and messages won\'t be posted.\n`!stars hide <message ID>` - Removes a starred message from starboard using message ID.\n`!reactions clean <user> [count] [emoji]` - Removes reactions placed by specified user.')

    @Plugin.command('ping', level=-1)
    def ping(self, event):
        pre = time.time()
        post = (time.mktime(to_datetime(event.msg.id).timetuple()) - pre) / 1000
        msg = event.msg.reply(":eyes:")
        ping = (time.time() - pre) * 1000
        msg.edit(":eyes: `BOT: {}ms` `API: {}ms`".format(int(post), int(ping)))
