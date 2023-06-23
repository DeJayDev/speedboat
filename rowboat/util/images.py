from dominantcolors import get_dominant_colors_for


def get_dominant_colors(img):
    return get_dominant_colors_for(img, 1)


def get_dominant_colors_user(user, url=None):
    import requests
    from rowboat.redis import rdb
    from PIL import Image
    from io import BytesIO

    key = "avatar:color:{}".format(user.avatar)
    if rdb.exists(key):
        return int(rdb.get(key))
    else:
        r = requests.get(url or user.get_avatar_url())
        try:
            r.raise_for_status()
        except:
            return 0

        rgbcolor = get_dominant_colors(Image.open(BytesIO(r.content)))[0]
        # https://stackoverflow.com/a/8340936
        color = int(
            "%02x%02x%02x" % (rgbcolor[0], rgbcolor[1], rgbcolor[2]), 16
        )  
        rdb.set(key, color)

        return color


def get_dominant_colors_guild(guild, url=None):
    import requests
    from rowboat.redis import rdb
    from PIL import Image
    from io import BytesIO

    key = "guild:color:{}".format(guild.icon)
    if rdb.exists(key):
        return int(rdb.get(key))
    else:
        r = requests.get(url or guild.get_icon_url())
        try:
            r.raise_for_status()
        except:
            return 0

        rgbcolor = get_dominant_colors(Image.open(BytesIO(r.content)))[0]
        # https://stackoverflow.com/a/8340936
        color = int(
            "%02x%02x%02x" % (rgbcolor[0], rgbcolor[1], rgbcolor[2]), 16
        )
        rdb.set(key, color)

        return color
