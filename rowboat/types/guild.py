import os

from rowboat.types import DictField, Field, Model, SlottedModel, raw, rule_matcher, text


class PluginConfigObj(object):
    client = None


class PluginsConfig(Model):
    def __init__(self, inst, obj):
        self.client = None
        self.load_into(inst, obj)

    @classmethod
    def parse(cls, obj, *args, **kwargs):
        inst = PluginConfigObj()
        cls(inst, obj)
        return inst

    @classmethod
    def force_load_plugin_configs(cls):
        """
        This function can be called to ensure that this class will have all its
        attributes properly loaded, as they are dynamically set when plugin configs
        are defined.
        """
        plugins = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "..", "plugins"
        )
        for name in os.listdir(plugins):
            __import__("rowboat.plugins.{}".format(name.rsplit(".", 1)[0]))


class CommandOverrideConfig(SlottedModel):
    disabled = Field(bool, default=False)
    level = Field(int)


class CommandsConfig(SlottedModel):
    prefix = Field(str, default="")
    prefixes = Field(list, default=[])
    mention = Field(bool, default=False)
    overrides = Field(raw)

    def get_command_override(self, command):
        return rule_matcher(command, self.overrides or [])


class GuildConfig(SlottedModel):
    nickname = Field(text)
    commands = Field(CommandsConfig, default=None, create=False)
    levels = DictField(int, int)
    plugins = Field(PluginsConfig.parse)
