import re

import yaml
from disco.types.user import ActivityTypes, Status

# Emojis
GREEN_TICK_EMOJI_ID = 318468935047446529
RED_TICK_EMOJI_ID = 318468934938394626
GREEN_TICK_EMOJI = 'green_tick:{}'.format(GREEN_TICK_EMOJI_ID)
RED_TICK_EMOJI = 'red_tick:{}'.format(RED_TICK_EMOJI_ID)
STAR_EMOJI = '\U00002B50'

STATUS_EMOJI = {  # TODO: Update these
    Status.ONLINE: ':online:872578963896156252',
    Status.IDLE: ':idle:872578994028023869',
    Status.DND: ':dnd:872578984238546945',
    Status.INVISIBLE: ':offline:872579004597665902',
    Status.OFFLINE: ':offline:872579004597665902',
    ActivityTypes.STREAMING: ':streaming:872579013976150037',
}

BADGE_EMOJI = {
    'discord_employee': ':staffNew:872564761173319711',
    'discord_partner': ':partner:748668878363820173',
    'certified_moderator': ':DMD:872564749374726145',
    'hypesquad_events': ':hypesquad_events:699078007326900265',
    'house_bravery': ':hypesquad_bravery:699078006764732458',
    'house_brilliance': ':hypesquad_brilliance:699078006936961126',
    'house_balance': ':hypesquad_balance:699078006915727442',
    'early_supporter': ':early_supporter:699078007133962280',
    'bug_hunter_one': ':bughunter1:872564739434217472',
    'bug_hunter_two': ':bughunter2:699078007179968613',
    'verified_dev': ':verified_developer:699078007150739486',
    'verified_bot': ':verified_developer:699078007150739486'
}

SNOOZE_EMOJI = '\U0001f4a4'

# Regexes
INVITE_LINK_RE = re.compile(r'(?:http|https)?(?::)?(?://)?((?:dsc|dis|discord|invite).(?:gd|gg|io|me)/([a-zA-Z0-9\-]+))', re.I)
URL_RE = re.compile(r'(https?://[^\s]+)')
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F700-\U0001F77F"  # alchemical symbols
    "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    "\U00002702-\U000027B0"  # Dingbats
    "\U000024C2-\U0001F251"  
    "]+"
)
EMOJI_RE = re.compile(r'<a?:(.+):([0-9]+)>')
USER_MENTION_RE = re.compile('<@!?([0-9]+)>')

# IDs and such
ROWBOAT_GUILD_ID = 342506939340685312
ROWBOAT_USER_ROLE_ID = 730247685499650108
ROWBOAT_CONTROL_CHANNEL = 598682202464845845

# Discord Error codes
ERR_UNKNOWN_MESSAGE = 10008

# Etc
YEAR_IN_SEC = 60 * 60 * 24 * 365
CDN_URL = 'https://twemoji.maxcdn.com/v/latest/72x72/{}.png'
WEB_URL = 'https://speedboat.dejay.dev'

# Loaded from files
with open('data/badwords.txt', 'r') as f:
    BAD_WORDS = f.readlines()

# Merge in any overrides in the config
with open('config.yaml', 'r') as f:
    loaded = yaml.safe_load(f.read())
    locals().update(loaded.get('constants', {}))
