import os; os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import logging

from flask import Flask, g, session
from holster.flask_ext import Holster

from rowboat import ENV
from rowboat.sql import init_db
from rowboat.models.user import User

from rowboat.views.auth import auth
from rowboat.views.dashboard import dashboard
from rowboat.views.guilds import guilds
from rowboat.views.users import users

from yaml import safe_load

rowboat = Holster(Flask(__name__))
logging.getLogger('peewee').setLevel(logging.DEBUG)
rowboat.app.register_blueprint(auth)
rowboat.app.register_blueprint(dashboard)
rowboat.app.register_blueprint(guilds)
rowboat.app.register_blueprint(users)


@rowboat.app.before_first_request
def before_first_request():
    init_db(ENV)

    # PluginsConfig.force_load_plugin_configs()

    with open('config.yaml', 'r') as f:
        data = safe_load(f)

    rowboat.app.config.update(data['web'])
    rowboat.app.secret_key = data['web']['SECRET_KEY']
    rowboat.app.config['token'] = data.get('token')


@rowboat.app.before_request
def check_auth():
    g.user = None

    if 'uid' in session:
        g.user = User.with_id(session['uid'])


@rowboat.app.after_request
def save_auth(response):
    if g.user and 'uid' not in session:
        session['uid'] = g.user.id
    elif not g.user and 'uid' in session:
        del session['uid']

    return response


@rowboat.app.context_processor
def inject_data():
    return {'user': g.user}
