import yaml

from flask import Blueprint, g, jsonify

from rowboat.models.guild import Guild
from rowboat.util.decos import authed

webhooks = Blueprint('users', __name__, url_prefix='/api/webhooks')

#TODO: General twitch reminder, store when we subscribed to a topic
#      topics "expire" on twitches end after 10 days

@webhooks.route('/twitch')
def twitch():
    req = yaml.safe_load(request.json['data'])[0]
    game = #TODO: GET https://api.twitch.tv/helix/games?id= req.i

    #TODO: Nullcheck for empty data array. That means stream went offline.
    """
    Send to Redis: 
    {
        "user": req.user_name, 
        "title": req.title,
        "game": game,
        "started_at": req.started_at,
        "thumbnail: req.thumbnail_url
    }
    """
    return 'ok'

@webhooks.route('/twitch/callback')
def twitch_callback():
    return request.values.get('hub.challenge')

@webhooks.route('/@me/guilds')
@authed
def users_me_guilds():
    if g.user.admin:
        guilds = list(Guild.select())
    else:
        guilds = list(Guild.select(
            Guild,
            Guild.config['web'][str(g.user.user_id)].alias('role')
        ).where(
            (~(Guild.config['web'][str(g.user.user_id)] >> None))
        ))

    return jsonify([
        guild.serialize() for guild in guilds
    ])
