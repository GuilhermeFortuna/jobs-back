"""String enums persisted as constrained VARCHAR values (not PostgreSQL ENUMs)."""

from enum import StrEnum


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class RemoteType(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"
    UNSPECIFIED = "unspecified"


class SalaryPeriod(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    OTHER = "other"


class JobStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SyncMode(StrEnum):
    FULL_SNAPSHOT = "full_snapshot"
    INCREMENTAL = "incremental"


class SyncRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SyncTrigger(StrEnum):
    MANUAL = "manual"
