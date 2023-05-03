from rowboat.models.migrations import Migrate


@Migrate.always()
def remove_premium(m):
    m.execute('ALTER TABLE guilds DROP COLUMN premium_sub_id')
