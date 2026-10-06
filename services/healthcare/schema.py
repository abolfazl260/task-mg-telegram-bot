"""Healthcare compatibility exports for the Core operational schema.

Healthcare no longer owns persistence. New code must use services.operations;
this module remains only to avoid breaking older imports during migration.
"""

from services.operations.schema import SCHEMA, TASK_COLUMNS, migrate

migrate_healthcare = migrate

__all__ = ["SCHEMA", "TASK_COLUMNS", "migrate", "migrate_healthcare"]
