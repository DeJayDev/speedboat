from rowboat.models.migrations import Migrate


@Migrate.always()
def drop_discrims(m):
    Migrate.execute("ALTER TABLE users DROP COLUMN discriminator;")
