from rowboat.models.migrations import Migrate
from rowboat.models.guild import Guild


@Migrate.always()
def remove_premium(m):
    m.execute('ALTAR TABLE guilds DROP COLUMN premium_sub_id')
