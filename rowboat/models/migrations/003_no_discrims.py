from rowboat.models.migrations import Migrate


@Migrate.always()
def drop_discrims(m):
    m.execute("ALTER TABLE users DROP COLUMN discriminator;")
