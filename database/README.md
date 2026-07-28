# Database Migrations

Cmdarr applies schema changes through the ledger-based migration system in
`database/version_migrations.py`. Migrations run at application startup, including
for Docker installations with existing data.

## How It Works

`create_version_migration_runner()` registers `VersionMigration` instances in
application order. The runner records each successful migration by name in the
`schema_migration` ledger, so only migrations that have not already been recorded
are applied. Version strings are release metadata; they do not determine whether a
migration runs.

## Adding New Migrations

Add a migration function and register it in
`create_version_migration_runner()`:

```python
def add_new_feature(cursor):
    # Make the operation safe for an existing database.
    cursor.execute("ALTER TABLE some_table ADD COLUMN new_column TEXT;")

runner.add_migration(VersionMigration(
    name="add_new_feature",
    version="0.3.19",
    description="Add new feature to some_table",
    up_func=add_new_feature
))
```

## Migration Guidelines

1. Use a descriptive, stable `name`; it is the ledger key.
2. Use a string release version such as `"0.3.19"`.
3. Make the migration safe for databases that already contain the target schema.
4. Provide `applied_check` when needed to backfill the ledger for previously applied
   schema changes.
5. Test migrations against a copy of production data.

## Running Migrations

Migrations run automatically at startup. Development builds can invoke
`run_version_migrations_manual()` from `database/version_migrations.py` to run the
same pending ledger entries manually.

## Troubleshooting

If migrations fail:
1. Check the logs for specific error messages
2. Verify the database file exists and is accessible
3. Ensure the migration logic handles existing data correctly
4. Test the migration on a copy of the database first
