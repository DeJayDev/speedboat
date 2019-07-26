import yaml

with open('config.yaml', 'r') as f:
    loaded = yaml.safe_load(f.read())
    locals().update(loaded)
