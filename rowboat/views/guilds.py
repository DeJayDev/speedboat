import functools
import json
import operator
from functools import reduce

import cchardet as chardet
import yaml
from flask import Blueprint, g, jsonify, request
from yaml.cyaml import CDumper

from rowboat.models.channel import Channel
from rowboat.models.guild import Guild, GuildConfigChange
from rowboat.models.message import Message
from rowboat.models.user import Infraction, User
from rowboat.util.decos import authed

guilds = Blueprint('guilds', __name__, url_prefix='/api/guilds')


def serialize_user(u):
    return {
        'user_id': str(u.user_id),
        'username': u.username,
    }


def with_guild(f=None):
    def deco(f):
        @authed
        @functools.wraps(f)
        def func(*args, **kwargs):
            try:
                if g.user.admin:
                    guild = Guild.select().where(Guild.guild_id == kwargs.pop('gid')).get()
                    guild.role = 'admin'
                else:
                    guild = Guild.select(
                        Guild,
                        Guild.config['web'][str(g.user.user_id)].alias('role')
                    ).where(
                        (Guild.guild_id == kwargs.pop('gid')) &
                        (~(Guild.config['web'][str(g.user.user_id)] >> None))
                    ).get()

                return f(guild, *args, **kwargs)
            except Guild.DoesNotExist:
                return 'Invalid Guild', 404

        return func

    if f and callable(f):
        return deco(f)

    return deco


@guilds.route('/<gid>')
@with_guild
def guild_get(guild):
    return jsonify(guild.serialize())


@guilds.route('/<gid>/config')
@with_guild
def guild_config(guild):
    encoding = chardet.detect(guild.config_raw.tobytes())['encoding']
    return jsonify({
        'contents': guild.config_raw.tobytes().decode(encoding) if guild.config_raw else yaml.dump(guild.config, allow_unicode=True, dumper=CDumper),
    })


@guilds.route('/<gid>/config', methods=['POST'])
@with_guild
def guild_z_config_update(guild):
    if guild.role not in ['admin', 'editor']:
        return 'Missing Permissions', 403

    # Calculate users diff
    try:
        data = yaml.safe_load(request.json['config'])
    except:
        return 'Invalid YAML', 400

    before = sorted(list(guild.config.get('web', {}).items()), key=lambda i: i[0])
    after = sorted([(str(k), v) for k, v in list(data.get('web', {}).items())], key=lambda i: i[0])

    if guild.role != 'admin' and before != after:
        return 'Invalid Access', 403

    role = data.get('web', {}).get(g.user.user_id) or data.get('web', {}).get(str(g.user.user_id))
    if guild.role != role and not g.user.admin:
        return 'Cannot change your own permissions', 400

    if data.get('modlog', {}):
        for modlog in data.get('modlog', {}).get('channels'):
            try:
                _mod = Channel.get(channel_id=modlog, guild_id=guild.guild_id)
            except Channel.DoesNotExist:
                return 'No modlog exists with id {}'.format(modlog), 400

    if data.get('starboard', {}):
        for starboard in data.get('starboard', {}).get('channels'):
            try:
                _starboard = Channel.get(channel_id=starboard, guild_id=guild.guild_id)
            except Channel.DoesNotExist:
                return u'No channel exists with id {}'.format(starboard), 400

    try:
        guild.update_config(g.user.user_id, request.json['config'])
        return '', 200
    except Guild.DoesNotExist:
        return 'Invalid Guild', 404
    except Exception as e:
        return 'Invalid Data: %s' % e, 400


CAN_FILTER = ['id', 'user_id', 'actor_id', 'type', 'reason']
CAN_SORT = ['id', 'user_id', 'actor_id', 'created_at', 'expires_at', 'type']


@guilds.route('/<gid>/infractions')
@with_guild
def guild_infractions(guild):
    user = User.alias()
    actor = User.alias()

    page = int(request.values.get('page', 1))
    if page < 1:
        page = 1

    limit = int(request.values.get('limit', 1000))
    if limit < 1 or limit > 1000:
        limit = 1000

    q = Infraction.select(Infraction, user, actor).join(
        user,
        on=((Infraction.user_id == user.user_id).alias('user'))
    ).switch(Infraction).join(
        actor,
        on=((Infraction.actor_id == actor.user_id).alias('actor'))
    )

    queries = list()
    if 'filtered' in request.values:
        filters = json.loads(request.values['filtered'])

        for f in filters:
            if f['id'] not in CAN_FILTER:
                continue

            if f['id'] == 'type':
                queries.append(Infraction.type_ == Infraction.Types.get(f['value']))
            elif f['id'] == 'reason':
                queries.append(Infraction.reason ** ('%' + f['value'].lower().replace('%', '') + '%'))
            else:
                queries.append(getattr(Infraction, f['id']) == f['value'])

    if queries:
        q = q.where(
            (Infraction.guild_id == guild.guild_id) &
            reduce(operator.and_, queries)
        )
    else:
        q = q.where((Infraction.guild_id == guild.guild_id))

    sorted_fields = list()
    if 'sorted' in request.values:
        sort = json.loads(request.values['sorted'])

        for s in sort:
            if s['id'] not in CAN_SORT:
                continue

            if s['desc']:
                sorted_fields.append(
                    getattr(Infraction, s['id']).desc()
                )
            else:
                sorted_fields.append(
                    getattr(Infraction, s['id'])
                )

    if sorted_fields:
        q = q.order_by(*sorted_fields)
    else:
        q = q.order_by(Infraction.id.desc())

    q = q.paginate(
        page,
        limit,
    )

    return jsonify([i.serialize(guild=guild, user=i.user, actor=i.actor) for i in q])


@guilds.route('/<gid>/config/history')
@with_guild
def guild_config_history(guild):
    def serialize(gcc):
        return {
            'user': serialize_user(gcc.user_id),
            'before': str(gcc.before_raw),
            'after': str(gcc.after_raw),
            'created_at': gcc.created_at.isoformat(),
        }

    q = GuildConfigChange.select(GuildConfigChange, User).join(
        User, on=(User.user_id == GuildConfigChange.user_id),
    ).where(GuildConfigChange.guild_id == guild.guild_id).order_by(
        GuildConfigChange.created_at.desc()
    ).paginate(int(request.values.get('page', 1)), 25)

    return jsonify(list(map(serialize, q)))


@guilds.route('/<gid>/stats/messages', methods=['GET'])
@with_guild()
def guild_stats_messages(guild):
    unit = request.values.get('unit', 'days')
    amount = int(request.values.get('amount', 7))

    sql = '''
        SELECT date, coalesce(count, 0) AS count
        FROM
            generate_series(
                NOW() - interval %s,
                NOW(),
                %s
            ) AS date
        LEFT OUTER JOIN (
            SELECT date_trunc(%s, timestamp) AS dt, count(*) AS count
            FROM messages
            WHERE
                timestamp >= (NOW() - interval %s) AND
                timestamp < (NOW()) AND
                guild_id=%s AND
            GROUP BY dt
        ) results
        ON (date_trunc(%s, date) = results.dt);
    '''

    tuples = list(Message.raw(
        sql,
        '{} {}'.format(amount, unit),
        '1 {}'.format(unit),
        unit,
        '{} {}'.format(amount, unit),
        guild.guild_id,
        unit
    ).tuples())

    return jsonify(tuples)
