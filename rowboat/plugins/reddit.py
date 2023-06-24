import json
from collections import defaultdict

import emoji
import requests
from disco.types.message import MessageEmbed

from rowboat.models.guild import Guild
from rowboat.plugins import RowboatPlugin as Plugin
from rowboat.redis import rdb
from rowboat.types import ChannelField, DictField, Field, SlottedModel
from rowboat.types.plugin import PluginConfig


class FormatMode:
    PLAIN = 'PLAIN'
    PRETTY = 'PRETTY'


class SubRedditConfig(SlottedModel):
    channel = Field(ChannelField)
    mode = Field(FormatMode, default=FormatMode.PRETTY)
    nsfw = Field(bool, default=False)
    text_length = Field(int, default=256)
    include_stats = Field(bool, default=False)


class RedditConfig(PluginConfig):
    # TODO: validate they have less than 3 reddits selected
    subs = DictField(str, SubRedditConfig)

    def validate(self):
        if len(self.subs) > 3:
            raise Exception('Cannot have more than 3 subreddits configured')

        # TODO: validate each subreddit


@Plugin.with_config(RedditConfig)
class RedditPlugin(Plugin):
    @Plugin.schedule(30, init=False)
    def check_subreddits(self):
        # TODO: sharding
        # TODO: filter in query
        subs_raw = list(Guild.select(
            Guild.guild_id,
            Guild.config['plugins']['reddit']
        ).where(
            ~(Guild.config['plugins']['reddit'] >> None)
        ).tuples())

        # Group all subreddits, iterate, update channels

        subs = defaultdict(list)

        for gid, config in subs_raw:
            config = json.loads(config)

            for k, v in list(config['subs'].items()):
                subs[k].append((gid, SubRedditConfig(v)))

        for sub, configs in list(subs.items()):
            try:
                self.update_subreddit(sub, configs)
            except requests.HTTPError:
                self.log.exception('Error loading sub %s:', sub)

    def get_channel(self, guild, ref):
        # CLEAN THIS UP TO A RESOLVER
        if isinstance(ref, int):
            return guild.channels.get(ref)
        else:
            return guild.channels.select_one(name=ref)

    def send_post(self, config, channel, data):
        if config.mode is FormatMode.PLAIN:
            channel.send_message('**{}**\n{}'.format(
                data['title'],
                'https://reddit.com{}'.format(data['permalink'])
            ))
        else:
            embed = MessageEmbed()

            if 'nsfw' in data and data['nsfw']:
                if not config.nsfw:
                    return
                embed.color = 0xED4245
            else:
                embed.color = 0xaecfc8

            # Limit title to 256 characters nicely
            if len(data['title']) > 256:
                embed.title = data['title'][:253] + '...'
            else:
                embed.title = data['title']

            embed.url = 'https://reddit.com{}'.format(data['permalink'])
            embed.set_author(
                name=data['author'],
                url='https://reddit.com/u/{}'.format(data['author'])
            )

            image = None

            if data.get('media'):
                if 'oembed' in data['media']:
                    image = data['media']['oembed']['thumbnail_url']
            elif data.get('preview'):
                if 'images' in data['preview']:
                    image = data['preview']['images'][0]['source']['url']

            if 'selftext' in data and data['selftext']:
                # TODO: better place for validation
                sz = min(64, max(config.text_length, 1900))
                embed.description = data['selftext'][:sz]
                if len(data['selftext']) > sz:
                    embed.description += '...'
                if image:
                    embed.set_thumbnail(url=image)
            elif image:
                embed.set_image(url=image)

            if config.include_stats:
                embed.set_footer(text=emoji.emojize('{} upvotes | {} downvotes | {} comments'.format(
                    data['ups'], data['downs'], data['num_comments']
                )))

            channel.send_message(embeds=[embed])

    def update_subreddit(self, sub, configs):
        # TODO: use before on this request
        r = requests.get(
            'https://www.reddit.com/r/{}/new.json'.format(sub),
            headers={
                'User-Agent': 'discord:Speedboat:v1.8.0 (by /u/dejaydev)'
            }
        )
        r.raise_for_status()

        data = list(reversed([i['data'] for i in r.json()['data']['children']]))

        # TODO:
        #  1. instead of tracking per guild, just track globally per subreddit
        #  2. fan-out posts to each subscribed channel

        for gid, config in configs:
            guild = self.state.guilds.get(gid)
            if not guild:
                self.log.warning('Skipping non existent guild %s', gid)
                continue

            channel = self.get_channel(guild, config.channel)
            if not channel:
                self.log.warning('Skipping non existent channel %s for guild %s (%s)', channel, guild.name, gid)
                continue
            last = float(rdb.get('rdt:lpid:{}:{}'.format(channel.id, sub)) or 0)

            item_count, high_time = 0, last
            for item in data:
                if item['created_utc'] > last:
                    try:
                        self.send_post(config, channel, item)
                    except:
                        self.log.exception('Failed to post reddit content from %s\n\n', item)
                    item_count += 1

                    if item['created_utc'] > high_time:
                        rdb.set('rdt:lpid:{}:{}'.format(channel.id, sub), item['created_utc'])
                        high_time = item['created_utc']

                if item_count > 10:
                    break
