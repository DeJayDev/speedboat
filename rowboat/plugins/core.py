import contextlib
import functools
import inspect
import json
import os
import pprint
import signal
from datetime import datetime, timedelta, timezone

from disco.api.http import APIException
from disco.bot import Bot
from disco.bot.command import CommandEvent
from disco.gateway.events import MessageCreate
from disco.types.message import MessageEmbed
from disco.types.permissions import Permissions
from disco.util.emitter import Emitter
from disco.util.sanitize import S
from disco.util.snowflake import to_datetime

from rowboat import ENV, REV
from rowboat.constants import GREEN_TICK_EMOJI, GREEN_TICK_EMOJI_ID, RED_TICK_EMOJI, RED_TICK_EMOJI_ID, ROWBOAT_CONTROL_CHANNEL, ROWBOAT_GUILD_ID, ROWBOAT_USER_ROLE_ID, WEB_URL
from rowboat.models.guild import Guild, GuildBan
from rowboat.models.message import Command, Message
from rowboat.models.user import Infraction
from rowboat.plugins import CommandFail, CommandResponse, CommandSuccess
from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.plugins.modlog import Actions
from rowboat.redis import rdb
from rowboat.sql import init_db
from rowboat.util import LocalProxy
from rowboat.util.formatting import DiscordFormatting, as_discord
from rowboat.util.stats import timed

PY_CODE_BLOCK = '```py\n{}\n```'

BOT_INFO = '''
Speedboat is a moderation and utilitarian bot built for large Discord servers.
'''

GUILDS_WAITING_SETUP_KEY = 'gws'


class CorePlugin(Plugin):
    def load(self, ctx):
        init_db(ENV)

        self.startup = ctx.get('startup', datetime.now(timezone.utc))
        self.guilds = ctx.get('guilds', {})

        self.emitter = Emitter()

        super(CorePlugin, self).load(ctx)

        # Overwrite the main bot instances plugin loader so we can magicify events
        self.bot.add_plugin = self.our_add_plugin

        # self.spawn(self.wait_for_plugin_changes)

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

    # def wait_for_plugin_changes(self):
    #     import gevent_inotifyx as inotify
    #     fd = inotify.init()
    #     inotify.add_watch(fd, 'rowboat/plugins/', inotify.IN_MODIFY)
    #     inotify.add_watch(fd, 'rowboat/plugins/modlog', inotify.IN_MODIFY)
    #     while True:
    #         events = inotify.get_events(fd)
    #         for event in events:
    #             # Can't reload core.py
    #             if event.name.startswith('core.py'):
    #                 continue
    #             plugin_name = '{}Plugin'.format(event.name.split('.', 1)[0].title())
    #             plugin = next((v for k, v in list(self.bot.plugins.items()) if k.lower() == plugin_name.lower()), None)
    #             if plugin:
    #                 self.log.info('Detected change in %s, reloading...', plugin_name)
    #                 try:
    #                     plugin.reload()
    #                 except:
    #                     self.log.exception('Failed to reload: ')

    def wait_for_actions(self):
        ps = rdb.pubsub()
        ps.subscribe('actions')

        for item in ps.listen():
            if item['type'] != 'message':
                continue

            data = json.loads(item['data'])
            if data['type'] == 'GUILD_UPDATE' and data['id'] in self.guilds:
                with self.send_control_message() as embed:
                    embed.title = 'Reloaded config for {}'.format(
                        self.guilds[data['id']].name
                    )

                self.log.info('Reloading guild %s', self.guilds[data['id']].name)

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
                    self.log.exception('Failed to reload config for guild %s', self.guilds[data['id']].name)
                    continue
            elif data['type'] == 'RESTART':
                self.log.info('Restart requested, signaling parent')
                os.kill(os.getppid(), signal.SIGUSR1)

    def unload(self, ctx):
        ctx['guilds'] = self.guilds
        ctx['startup'] = self.startup
        super(CorePlugin, self).unload(ctx)

    def update_rowboat_guild_access(self):
        if ROWBOAT_GUILD_ID not in self.state.guilds or ENV != 'prod':
            return

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

            for user_id in list(guild.config['web'].keys()):
                try:
                    users_who_should_have_access.add(int(user_id))
                except:
                    self.log.warning('Guild %s has invalid user ACLs: %s', guild.guild_id, guild.config['web'])

        # TODO: sharding
        users_who_have_access = {
            i.id for i in list(rb_guild.members.values())
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

    def crab(self):
        return 'crab'

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
                (Guild.last_ban_sync < (datetime.now(timezone.utc) - timedelta(days=1))) |
                (Guild.last_ban_sync >> None)
            )
            if guild.guild_id in self.client.state.guilds]

        # Update 10 at a time
        for guild in to_update[:10]:
            guild.sync_bans(self.client.state.guilds.get(guild.guild_id))

    @Plugin.listen('GuildUpdate')
    def on_guild_update(self, event):
        self.log.info('Got guild update for guild %s (%s)', event.guild.name, event.guild.id)

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
        embed.timestamp = datetime.now(timezone.utc).isoformat()
        embed.color = 0x5865F2
        try:
            yield embed
            self.bot.client.api.channels_messages_create(
                ROWBOAT_CONTROL_CHANNEL,
                embeds=[embed]
            )
        except:
            self.log.exception('Failed to send control message:')
            return

    @Plugin.listen('Resumed')
    def on_resumed(self, event):
        with self.send_control_message() as embed:
            embed.title = 'Resumed'
            embed.color = 0xFEE75C
            embed.add_field(name='Replayed Events', value=str(self.client.gw.replayed_events))

    #@Plugin.listen('Ready', priority=Priority.SEQUENTIAL)
    @Plugin.listen('Ready')
    def on_ready(self, event):
        reconnects = self.client.gw.reconnects
        self.log.info('Started session {} (reconnects {})'.format(event.session_id, reconnects))

        with self.send_control_message() as embed:
            if reconnects:
                embed.title = 'Reconnected'
                embed.color = 0xFEE75C
            else:
                embed.title = 'Connected'
                embed.color = 0x57F287

    #@Plugin.listen('GuildCreate', priority=Priority.SEQUENTIAL, conditional=lambda e: not e.created)
    @Plugin.listen('GuildCreate')
    def on_guild_create(self, event):
        try:
            guild = Guild.with_id(event.guild.id)
        except Guild.DoesNotExist:
            # If the guild is not awaiting setup, leave it now
            if not rdb.sismember(GUILDS_WAITING_SETUP_KEY, str(event.guild.id)) and event.guild.id != ROWBOAT_GUILD_ID:
                self.log.warning(
                    'Guild %s (%s) is awaiting setup.',
                    event.guild.id, event.guild.name
                )
            return
        except Exception as e:
            self.log.error("Failed to get guild {} because {}".format(event.guild.id, e))

        if not guild.enabled:
            return

        config = guild.get_config()
        if not config:
            return

        # Ensure we're updated
        self.log.info('Requesting Guild: %s (%s)', event.guild.name, event.guild.id)
        guild.sync(event.guild)

        #guild.request_guild_members()

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
    def on_message_create(self, event: MessageCreate):
        """
        This monstrosity of a function handles the parsing and dispatching of
        commands.
        """
        if event.message.author.bot:
            return

        if event.guild_id:
            if not event.message.channel.get_permissions(self.state.me).can(Permissions.SEND_MESSAGES, Permissions.VIEW_CHANNEL):
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

        if config and config.commands:
            # If the guild has configuration, use that (otherwise use defaults)
            commands = list(self.bot.get_commands_for_message(
                    config.commands.mention,
                    {},
                    config.commands.prefix if config.commands.prefix else config.commands.prefixes,
                    event.message))
        elif ENV != 'prod':
            if event.message.content.startswith(ENV + '!'):
                commands = list(self.bot.get_commands_for_message(False, {}, [ENV + '!'], event.message))
            else:
                return # fast fail, commands isn't set so we won't make it to the if not len commands check.
        elif guild_id:
            # Otherwise, default to requiring mentions
            commands = list(self.bot.get_commands_for_message(True, {}, '', event.message))
        else:
            # DM's just use the commands (no prefix/mention)
            commands = list(self.bot.get_commands_for_message(False, {}, '', event.message))

        # If we didn't find any matching commands, return
        if not len(commands):
            return

        event.user_level = self.get_level(event.guild, event.author) if event.guild else 0

        # Grab whether this user is a global admin
        # TODO: Get this from the database instead of Redis
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

            if level is None:
                level = 0

            if not global_admin and event.user_level < level:
                continue

            with timed('rowboat.command.duration', tags={'plugin': command.plugin.name, 'command': command.name}):
                try:
                    command_event = CommandEvent(command, event, match)
                    command_event.user_level = event.user_level
                    command.plugin.execute(command_event)
                except CommandResponse as e:
                    event.reply(e.response)
                except:
                    tracked = Command.track(event, command, exception=True)
                    self.log.exception('Command Error:')

                    with self.send_control_message() as embed:
                        embed.title = 'Command Error: {}'.format(command.name)
                        embed.color = 0xED4245
                        embed.add_field(
                            name='Author', value='({}) `{}`'.format(event.author, event.author.id), inline=True)
                        embed.add_field(name='Channel', value='({}) `{}`'.format(
                            event.channel.name,
                            event.channel.id
                        ), inline=True)
                        embed.description = '```{}```'.format('\n'.join(tracked.traceback.split('\n')[-8:]))

                    return event.reply('<:{}> something went wrong, perhaps try again later'.format(RED_TICK_EMOJI))

            Command.track(event, command)

            # Dispatch the command used modlog event
            if config:
                modlog_config = getattr(config.plugins, 'modlog', None)
                if not modlog_config:
                    return

                self._attach_local_event_data(event, 'modlog', event.guild.id)

                modlog = self.bot.plugins.get('ModLogPlugin')
                if modlog:
                    modlog.log_action(Actions.COMMAND_USED, event)

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
        m = event.guild.members.get(self.state.me.id)
        if not m.permissions.administrator and not global_admin:
            raise CommandFail('Bot must have the Administrator permission')

        guild = Guild.setup(event.guild)
        rdb.srem(GUILDS_WAITING_SETUP_KEY, str(event.guild.id))
        self.guilds[event.guild.id] = guild
        raise CommandSuccess('Successfully loaded configuration')

    @Plugin.command('nuke', '<user:snowflake> <reason:str...>', level=-1)
    def nuke(self, event, user, reason):
        contents = list()

        for gid, guild in list(self.guilds.items()):
            guild = self.state.guilds[gid]
            perms = guild.get_permissions(self.state.me)

            if not perms.ban_members and not perms.administrator:
                contents.append(':x: {} - Could not Ban'.format(
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
                contents.append(':x: {} - Error'.format(
                    guild.name
                ))
                self.log.exception('Failed to force ban %s in %s', user, gid)

            contents.append(':white_check_mark: {} - :regional_indicator_f:'.format(
                guild.name
            ))

        event.msg.reply('The Damage:\n' + '\n'.join(contents))

    @Plugin.command('unnuke', '<user:snowflake> <reason:str...>', level=-1)
    def unnuke(self, event, user, reason):
        contents = list()

        for gid, guild in list(self.guilds.items()):
            guild = self.state.guilds[gid]
            perms = guild.get_permissions(self.state.me)

            if not perms.ban_members and not perms.administrator:
                contents.append(':x: {} - Could not Unban'.format(
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
                contents.append(':x: {} - Error'.format(
                    guild.name
                ))
                self.log.exception('Failed to remove ban for %s in %s', user, gid)

            contents.append(':white_check_mark: {} - Fixed :heart:'.format(
                guild.name
            ))

        event.msg.reply('Result:\n' + '\n'.join(contents))

    @Plugin.command('about')
    def command_about(self, event):    
        embed = MessageEmbed()
        embed.set_author(name='Speedboat', icon_url=self.client.state.me.avatar_url, url=WEB_URL)
        embed.description = BOT_INFO
        embed.add_field(name='Servers', 
                        value=str(len(self.state.guilds)), 
                        inline=True)
        embed.add_field(name='Last Started', 
                        value='{}'.format(as_discord(self.startup, DiscordFormatting.RELATIVE)), 
                        inline=True)
        embed.add_field(name='Version',
                        value=REV,
                        inline=True)
        event.msg.reply(embeds=[embed])

    @Plugin.command('uptime', level=-1)
    def command_uptime(self, event):
        event.msg.reply('Speedboat was started {}'.format(as_discord(self.startup)))

    @Plugin.command('source', '<command>', level=-1)
    def command_source(self, event, command=None):
        for cmd in self.bot.commands:
            if command.lower() in cmd.triggers:
                break
        else:
            raise CommandFail(
                "Couldn't find command `{}` (try being specific)".format(S(command, escape_codeblocks=True)))

        code = cmd.func.__code__
        length, firstline = inspect.getsourcelines(code)

        event.msg.reply('<https://github.com/DeJayDev/speedboat/blob/master/{}#L{}-L{}>'.format(
            code.co_filename.replace('/home/speedboat/speedboat/', ''),
            firstline,
            firstline + len(length)  # length length
        ))

    @Plugin.command('eval', level=-1)
    def command_eval(self, event):
        ctx = {
            'self': self,
            'bot': self.bot,
            'client': self.bot.client,
            'api': self.bot.client.api,
            'state': self.bot.client.state,
            'event': event,
            'msg': event.msg,
            'message': event.msg,
            'guild': event.msg.guild,
            'channel': event.msg.channel,
            'member': event.msg.member,
            'author': event.msg.author,
            'crab': '🦀'
        }

        # Multiline eval
        src = event.codeblock
        if src.count('\n'):
            lines = list(filter(bool, src.split('\n')))
            if lines[-1] and 'return' not in lines[-1]:
                lines[-1] = 'return ' + lines[-1]
            lines = '\n'.join('    ' + i for i in lines)
            code = 'def f():\n{}\nx = f()'.format(lines)
            local = {}

            try:
                exec(compile(code, '<eval>', 'exec'), ctx, local)
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
        self.client.gw.ws.close()
        raise CommandSuccess('Closing connection')

    @Plugin.command('invite', '<guild:snowflake>', aliases=['inv'], group='guilds', level=-1)
    def guild_join(self, event, guild):
        guild = self.state.guilds.get(guild)
        if not guild:
            return event.msg.reply(':no_entry_sign: invalid or unknown guild ID')

        msg = event.msg.reply('Ok, hold on while I get you setup with an invite link to {}'.format(
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
            return msg.edit(':no_entry_sign: Hmmm, something went wrong creating an invite for {}'.format(
                guild.name,
            ))

        msg.edit("Ok, here's that temporary invite for you: discord.gg/{}".format(
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

    @Plugin.command('config')
    def config_cmd(self, event):
        raise CommandSuccess('{}/guilds/{}/config'.format(WEB_URL, event.guild.id))

    # extract the msg selecting and confirmation bit to a function
    # allow me to purge messages from the database specifically w/o discord 
    # allow me to purge messages from the database that are only marked deleted in the db
    @Plugin.command('gdpr', '<user:snowflake> [target:snowflake] {channel} {guild} {everywhere} {discordtoo}', group='control', level=-1)
    def gdpr_cmd(self, event, user, target, channel=False, guild=False, everywhere=False, discordtoo=False):
        if not any([channel, guild, everywhere]):
            raise CommandFail("Please flag either channel, guild, or everywhere.")

        bot_reply = event.channel.send_message("Loading user messages...")

        q = Message.select().where(
            Message.author == user
        )
        
        if channel:
            q.where(Message.channel_id == target)
        if guild:
            q.where(Message.guild_id == target)
        if everywhere:
            event.msg.reply(":rotating_light: **HEY!** You are using everywhere mode. Proceed with caution.").after(10).delete()

        messages = list(q)

        bot_reply.delete()

        if not discordtoo:
            event.msg.reply("You've asked me not to delete Discord messages")

        if discordtoo:
            confirm_msg = event.msg.reply(':warning: You have selected {} messages from {} in {}. Are you sure you wish to continue deleting?'.format(
                len(messages),
                user,
                target if target else 'all known channels (everywhere)'
            ))

            confirm_msg.chain(False). \
                add_reaction(GREEN_TICK_EMOJI). \
                add_reaction(RED_TICK_EMOJI)

            try:
                mra_event = self.wait_for_event(
                    'MessageReactionAdd',
                    message_id=confirm_msg.id,
                    conditional=lambda e: (
                            e.emoji.id in (GREEN_TICK_EMOJI_ID, RED_TICK_EMOJI_ID) and
                            e.user_id == event.author.id
                    )).get(timeout=30)
            except gevent.Timeout:
                return
            finally:
                confirm_msg.delete()

            if mra_event.emoji.id != GREEN_TICK_EMOJI_ID:
                return

            event.msg.reply(':wastebasket: Ok. Please hold on, this may take a while - but I\'ll be back...')
            deleted = 0

            for message in messages:
                m: Message = message
                if message.deleted:
                    message.delete_instance()
                    continue # moving on.

                if state.channels[message.channel_id]:
                    self.bot.client.api.channels_messages_delete(message.channel_id, message.id)

                message.delete_instance()
                deleted = deleted + 1

            raise CommandSuccess("Done {} messages were deleted from Speedboat Database {}".format(
                deleted,
                'and Discord too' if discordtoo else ''
            ))
        
