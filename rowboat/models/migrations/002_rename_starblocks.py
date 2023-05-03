from rowboat.models.migrations import Migrate


@Migrate.always()
def rename_starblocks(m):
    m.execute('ALTER TABLE starboardblock RENAME TO starboardentity')