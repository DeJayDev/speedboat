import os

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import logging

from flask import Flask, g, session
from yaml import safe_load

from rowboat import ENV
from rowboat.models.user import User
from rowboat.sql import init_db
from rowboat.views.auth import auth
from rowboat.views.dashboard import dashboard
from rowboat.views.guilds import guilds
from rowboat.views.users import users

with open('config.yaml', 'r') as f:
    data = safe_load(f)

rowboat = Flask(__name__)
logging.getLogger('peewee').setLevel(logging.DEBUG)
rowboat.register_blueprint(auth)
rowboat.register_blueprint(dashboard)
rowboat.register_blueprint(guilds)
rowboat.register_blueprint(users)
rowboat.config.update(data['web'])
rowboat.secret_key = data['web']['SECRET_KEY']

init_db(ENV)

# PluginsConfig.force_load_plugin_configs()
# rowboat.config['token'] = data.get('token')

@rowboat.before_request
def check_auth():
    g.user = None

    if 'uid' in session:
        g.user = User.with_id(session['uid'])


@rowboat.after_request
def save_auth(response):
    if g.user and 'uid' not in session:
        session['uid'] = g.user.id
    elif not g.user and 'uid' in session:
        del session['uid']

    return response


@rowboat.context_processor
def inject_data():
    return {'user': g.user}
