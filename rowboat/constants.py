import re
import yaml
from disco.types.user import GameType, Status

# Emojis
GREEN_TICK_EMOJI_ID = 318468935047446529
RED_TICK_EMOJI_ID = 318468934938394626
GREEN_TICK_EMOJI = 'green_tick:{}'.format(GREEN_TICK_EMOJI_ID)
RED_TICK_EMOJI = 'red_tick:{}'.format(RED_TICK_EMOJI_ID)
STAR_EMOJI = '\U00002B50'
STATUS_EMOJI = {
    Status.ONLINE: ':status_online:318468935362281472',
    Status.IDLE: ':status_away:318468935387316234',
    Status.DND: ':status_dnd:318468935336984576',
    Status.OFFLINE: ':status_offline:318468935391641600',
    GameType.STREAMING: ':status_streaming:318468935450099712',
}
SNOOZE_EMOJI = '\U0001f4a4'

# Regexes
INVITE_LINK_RE = re.compile(r'(discordapp.com/invite|discord.me|discord.gg)(?:/#)?(?:/invite)?/([a-z0-9\-]+)', re.I)
URL_RE = re.compile(r'(https?://[^\s]+)')
EMOJI_RE = re.compile(r'<a?:(.+):([0-9]+)>')
USER_MENTION_RE = re.compile('<@!?([0-9]+)>')

# IDs and such
ROWBOAT_GUILD_ID = 342506939340685312
ROWBOAT_USER_ROLE_ID = 648955559541997578
ROWBOAT_CONTROL_CHANNEL = 598682202464845845

# Discord Error codes
ERR_UNKNOWN_MESSAGE = 10008

# Etc
YEAR_IN_SEC = 60 * 60 * 24 * 365
CDN_URL = 'https://twemoji.maxcdn.com/2/72x72/{}.png'

# Loaded from files
with open('data/badwords.txt', 'r') as f:
    BAD_WORDS = f.readlines()

# Merge in any overrides in the config
with open('config.yaml', 'r') as f:
    loaded = yaml.safe_load(f.read())
    locals().update(loaded.get('constants', {}))
