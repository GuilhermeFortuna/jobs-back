"""Manual CLI for provider ingestion."""

from __future__ import annotations

import argparse
import asyncio
import sys

from jobs_back.config import get_settings
from jobs_back.ingestion.service import (
    IngestionService,
    LockContention,
    SetupFailure,
    SyncRunFailure,
    SyncRunSuccess,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobs_back.ingestion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Run a provider sync")
    sync_parser.add_argument(
        "--provider",
        required=True,
        help="Provider key to sync",
    )
    return parser


def format_success(result: SyncRunSuccess) -> str:
    return (
        f"run_id={result.run_id} "
        f"fetched={result.fetched} "
        f"created={result.created} "
        f"updated={result.updated} "
        f"unchanged={result.unchanged} "
        f"reactivated={result.reactivated} "
        f"deactivated={result.deactivated}"
    )


def format_failure(result: SyncRunFailure) -> str:
    return (
        f"run_id={result.run_id} "
        f"error={result.error_code} "
        f"message={result.error_message}"
    )


def format_setup_failure(result: SetupFailure) -> str:
    return f"error={result.error_code} message={result.error_message}"


def format_lock_contention(result: LockContention) -> str:
    return f"error={result.error_code} message={result.error_message}"


async def run_sync(provider: str) -> int:
    settings = get_settings()
    service = IngestionService(settings)
    result = await service.run_sync(provider)

    if isinstance(result, SyncRunSuccess):
        print(format_success(result))
        return 0
    if isinstance(result, SyncRunFailure):
        print(format_failure(result))
        return 1
    if isinstance(result, SetupFailure):
        print(format_setup_failure(result))
        return 2
    if isinstance(result, LockContention):
        print(format_lock_contention(result))
        return 3
    msg = f"Unexpected sync result type: {type(result)!r}"
    raise TypeError(msg)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "sync":
        return asyncio.run(run_sync(args.provider))

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
