from rowboat.models.migrations import Migrate


@Migrate.always()
def rename_starblocks(m):
    Migrate.rename_column(m, 'starboardblock', 'user_id', 'entity_id')
