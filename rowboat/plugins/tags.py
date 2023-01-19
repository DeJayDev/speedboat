from disco.bot import CommandLevels
from disco.types.message import MessageEmbed
from disco.util.sanitize import S

from rowboat.models.tags import Tag
from rowboat.models.user import User
from rowboat.plugins import CommandFail, CommandSuccess
from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.types import Field
from rowboat.types.plugin import PluginConfig


class TagsConfig(PluginConfig):
    max_tag_length = Field(int, default=1950)
    min_level_remove_others = Field(int, default=int(CommandLevels.MOD))


@Plugin.with_config(TagsConfig)
class TagsPlugin(Plugin):
    @Plugin.command('create', '<name:str> <content:str...>', group='tag', aliases=['add', 'new'], level=CommandLevels.TRUSTED)
    def on_tags_create(self, event, name, content):
        name = S(name)
        content = S(content)

        if len(content) > event.config.max_tag_length:
            raise CommandFail('Tag content is too long (max {} characters)'.format(event.config.max_tag_length))

        _, created = Tag.get_or_create(
            guild_id=event.guild.id,
            author_id=event.author.id,
            name=name,
            content=content
        )

        if not created:
            raise CommandFail('A tag by that name already exists')

        raise CommandSuccess('ok, your tag named `{}` has been created'.format(name))

    @Plugin.command('list', group='tag', level=CommandLevels.TRUSTED)
    def on_tags_list(self, event):
        tags = Tag.select(Tag, User).join(
            User, on=(User.user_id == Tag.author_id)
        ).where(
            (Tag.guild_id == event.guild.id)
        ).order_by(Tag.name)

        if not tags:
            raise CommandFail('No tags exist')

        embed = MessageEmbed()
        embed.title = 'Tags for {}'.format(event.guild.name)
        embed.description = '\n'.join(
            '- `{}` by {}'.format(tag.name, tag.user.name)
            for tag in tags
        )

        event.msg.reply(embed=embed)

    @Plugin.command('tags', '<name:str>', aliases=['tag'], level=CommandLevels.TRUSTED)
    @Plugin.command('show', '<name:str>', group='tag', level=CommandLevels.TRUSTED)
    def on_tags(self, event, name):
        try:
            tag = Tag.select(Tag, User).join(
                User, on=(User.user_id == Tag.author_id)
            ).where(
                (Tag.guild_id == event.guild.id) &
                (Tag.name == S(name))
            ).get()
        except Tag.DoesNotExist:
            raise CommandFail('No tag by that name exists')

        # Track the usage of the tag
        Tag.update(times_used=Tag.times_used + 1).where(
            (Tag.guild_id == tag.guild_id) &
            (Tag.name == tag.name)
        ).execute()

        event.msg.reply(':information_source: {}'.format(
            tag.content
        ))

    @Plugin.command('remove', '<name:str>', group='tag', aliases=['del', 'rm'], level=CommandLevels.TRUSTED)
    def on_tags_remove(self, event, name):
        try:
            tag = Tag.select(Tag, User).join(
                User, on=(User.user_id == Tag.author_id)
            ).where(
                (Tag.guild_id == event.guild.id) &
                (Tag.name == S(name))
            ).get()
        except Tag.DoesNotExist:
            raise CommandFail('No tag by that name exists')

        if tag.author_id != event.author.id:
            if event.user_level <= event.config.min_level_remove_others:
                raise CommandFail('You do not have the required permissions to remove other users tags')

        tag.delete_instance()
        raise CommandSuccess('ok, deleted tag `{}`'.format(tag.name))

    @Plugin.command('info', '<name:str>', group='tag', level=CommandLevels.TRUSTED)
    def on_tags_info(self, event, name):
        try:
            tag = Tag.select(Tag, User).join(
                User, on=(User.user_id == Tag.author_id).alias('author')
            ).where(
                (Tag.guild_id == event.guild.id) &
                (Tag.name == S(name))
            ).get()
        except Tag.DoesNotExist:
            raise CommandFail('No tag by that name exists')

        embed = MessageEmbed()
        embed.title = tag.name
        embed.description = tag.content
        embed.add_field(name='Author', value=str(tag.author), inline=True)
        embed.add_field(name='Times Used', value=str(tag.times_used), inline=True)
        embed.timestamp = tag.created_at.isoformat()
        event.msg.reply(embed=embed)
