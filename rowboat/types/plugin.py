from rowboat.types import SlottedModel


class PluginConfig(SlottedModel):
    def load(self, obj, *args, **kwargs):
        obj = {
            k: v for k, v in obj.items()
            if k in self._fields and not self._fields[k].metadata.get('private')
        }
        return super(PluginConfig, self).load(obj, *args, **kwargs)
