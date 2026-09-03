"""Shared test helpers for creating Job rows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jobs_back.models.enums import EmploymentType, JobStatus, RemoteType
from jobs_back.models.job import Job


def make_job(**overrides: object) -> Job:
    now = datetime.now(tz=UTC)
    data: dict[str, object] = {
        "id": uuid.uuid4(),
        "provider": "example",
        "provider_job_id": f"job-{uuid.uuid4()}",
        "raw_payload": {"source": "test"},
        "title": "Software Engineer",
        "company": "Acme",
        "employment_type": EmploymentType.FULL_TIME.value,
        "remote_type": RemoteType.REMOTE.value,
        "job_url": "https://example.com/jobs/1",
        "status": JobStatus.ACTIVE.value,
        "discovered_at": now,
        "last_seen_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return Job(**data)  # type: ignore[arg-type]
