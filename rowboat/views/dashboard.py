import json
import subprocess
from datetime import datetime, timezone

from flask import Blueprint, g, make_response

from rowboat.models.message import MessageArchive
from rowboat.redis import rdb
from rowboat.util.decos import authed

dashboard = Blueprint('dash', __name__)


def pretty_number(i):
    return str(f"{i:,}")


class ServerSentEvent(object):
    def __init__(self, data):
        self.data = data
        self.event = None
        self.id = None
        self.desc_map = {
            self.data: "data",
            self.event: "event",
            self.id: "id"
        }

    def encode(self):
        if not self.data:
            return ""
        lines = ["%s: %s" % (v, k) for k, v in self.desc_map.items() if k]
        return "%s\n\n" % "\n".join(lines)


@dashboard.route('/api/archive/<aid>.<fmt>')
def archive(aid, fmt):
    try:
        archive = MessageArchive.select().where(
            (MessageArchive.archive_id == aid) &
            (MessageArchive.expires_at > datetime.now(timezone.utc))
        ).get()
    except MessageArchive.DoesNotExist:
        return 'Invalid or Expired Archive ID', 404

    mime_type = None
    if fmt == 'json':
        mime_type = 'application/json'
    elif fmt == 'txt':
        mime_type = 'text/plain'
    elif fmt == 'csv':
        mime_type = 'text/csv'

    res = make_response(archive.encode(fmt))
    res.headers['Content-Type'] = mime_type
    return res


@dashboard.route('/api/deploy', methods=['POST'])
@authed
def deploy():
    if not g.user.admin:
        return '', 401

    subprocess.Popen(['git', 'pull', 'origin', 'master']).wait()
    rdb.publish('actions', json.dumps({
        'type': 'RESTART',
    }))
    return '', 200
