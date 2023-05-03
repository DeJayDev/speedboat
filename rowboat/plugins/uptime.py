from disco.bot import Plugin
from flask import jsonify


class UptimePlugin(Plugin):
    @Plugin.route("/status")
    async def uptime(self):
        return jsonify({"success": True})
