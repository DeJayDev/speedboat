import hashlib
import hmac
import twitch as twitch_api
import yaml

from flask import Blueprint, g, request, jsonify, current_app

from rowboat.models.guild import Guild
from rowboat.util.decos import authed

webhooks = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')

#TODO: General twitch reminder, store when we subscribed to a topic
#      topics "expire" on twitches end after 10 days

@webhooks.route('/twitch')
def twitch():
    helix = twitch_api.Helix(current_app.config['TWITCH_CLIENT_ID'])
    secret = current_app.config['SECRET_KEY']
    
    expected = request.headers.get('x-hub-signature')
    calculated = hmac.new(bytes(secret, "utf-8"), request.data, digestmod=hashlib.sha256)

    if calculated is not expected:
        return 'no'

    req = yaml.safe_load(request.json['data'])[0]

    if req is None:
        msg = json.dumps({
            'type': "STREAM_OFFLINE" #TODO: Read this object more, 
            # I need to know WHO went offline.
        })

    game = None
    try:
        game = helix.game(req.i).name
    except:
        game = "Unknown Game"

    rdb.publish('media', json.dumps({
        'type': "STREAM_ONLINE",
        'user': req.user_name, 
        'title': req.title,
        'game': game,
        'started_at': req.started_at,
        'thumbnail': req.thumbnail_url
    }))
    return 'ok'

@webhooks.route('/twitch/callback')
def twitch_callback():
    return request.values.get('hub.challenge')

@webhooks.route('/mixer')
def mixer():
    secret = current_app.config['SECRET_KEY']

    expected = request.headers.get('x-hub-signature')
    calculated = hmac.new(bytes(secret, "utf-8"), request.data, digestmod=hashlib.sha384)

    if calculated is not expected:
        return 'no'

    req = yaml.safe_load(request.json['data'])[0]
    return 'hey microsoft :)'