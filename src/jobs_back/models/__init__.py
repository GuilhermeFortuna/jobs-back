"""ORM models. Import this package before Alembic reads Base.metadata."""

from jobs_back.models.enums import (
    EmploymentType,
    JobStatus,
    RemoteType,
    SalaryPeriod,
    SyncMode,
    SyncRunStatus,
    SyncTrigger,
)
from jobs_back.models.profile import Profile
from jobs_back.models.saved_job import SavedJob

# Batch 01 catalog models remain importable for historical ingestion code:
#   from jobs_back.models.job import Job
#   from jobs_back.models.sync_run import SyncRun

__all__ = [
    "EmploymentType",
    "JobStatus",
    "RemoteType",
    "Profile",
    "SalaryPeriod",
    "SavedJob",
    "SyncMode",
    "SyncRunStatus",
    "SyncTrigger",
]
