# Database Migrations

This directory contains the database migration system for Cmdarr. The migration system ensures that database schema changes are applied consistently across all environments, including Docker containers with existing data.

## How It Works

1. **Migration Framework**: `migration_framework.py` provides a robust system for defining and running migrations
2. **Migration Script**: `migrate.py` is the entry point that can be run standalone or integrated into the application
3. **Migration Tracking**: The `migrations` table tracks which migrations have been applied

## Adding New Migrations

To add a new migration, edit `database/migration_framework.py` and add a new migration to the `create_migration_runner()` function:

```python
def add_new_feature(cursor):
    # Your migration logic here
    cursor.execute("ALTER TABLE some_table ADD COLUMN new_column TEXT;")
    logger.info("Added new_column to some_table")

# For new migrations after app version change, use current app_version
runner.add_migration(Migration(
    name="add_new_feature",
    version=get_migration_version(1),  # First migration for new app version
    description="Add new feature to some_table",
    up_func=add_new_feature
))
```

## Migration Guidelines

1. **Always check if changes already exist** before applying them
2. **Use descriptive names** for migrations
3. **Use get_migration_version(sequence)** for version numbers (syncs with app version)
4. **Handle existing data** gracefully
5. **Test migrations** on a copy of production data

## Versioning

Migration versions are automatically generated based on the app version:
- App version `0.1.0` with sequence `1` becomes migration version `0.1.0.1`
- App version `0.1.0` with sequence `2` becomes migration version `0.1.0.2`
- When app version changes to `0.2.0`, new migrations become `0.2.0.1`, `0.2.0.2`, etc.

**Important**: All migrations created for the same app version should use the same base version for consistency. Existing migrations use pinned versions to maintain stability.

## Running Migrations

### In Development
```bash
python database/migrate.py
```

### In Docker
Migrations run automatically when the application starts, but you can also run them manually:
```bash
docker exec -it cmdarr python database/migrate.py
```

### Testing Migrations
```bash
python test_migration.py
```

## Migration History

- **v0.1.0.1**: Added `status` column to `command_executions` table
- **v0.1.0.2**: Ensured all required indexes exist on `command_executions` table
- **v0.1.0.3**: Added `timeout_minutes` column to `command_configs` table
- **v0.1.0.4**: Removed playlist sync config options from global config (now command-specific)

## Troubleshooting

If migrations fail:
1. Check the logs for specific error messages
2. Verify the database file exists and is accessible
3. Ensure the migration logic handles existing data correctly
4. Test the migration on a copy of the database first
