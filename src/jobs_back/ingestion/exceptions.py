"""Typed exceptions for provider ingestion."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Base class for ingestion errors with a stable operator-facing code."""

    error_code: str = "ingestion_error"
    operator_message: str = "An ingestion error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message or self.operator_message)
        self.cause = cause
        if cause is not None:
            logger.debug(
                "%s: %s",
                self.error_code,
                cause,
                exc_info=cause,
            )


class AdapterConfigurationError(IngestionError):
    error_code = "provider_not_configured"
    operator_message = "The selected provider is not configured."


class UnknownProviderError(IngestionError):
    error_code = "unknown_provider"
    operator_message = "The selected provider is not registered."


class AdapterAuthenticationError(IngestionError):
    error_code = "adapter_authentication_failed"
    operator_message = "Provider authentication failed."


class AdapterTransportError(IngestionError):
    error_code = "adapter_transport_failed"
    operator_message = "Provider transport failed."


class AdapterRateLimitError(IngestionError):
    error_code = "adapter_rate_limited"
    operator_message = "Provider rate limit exceeded."


class AdapterSchemaError(IngestionError):
    error_code = "adapter_schema_error"
    operator_message = "Provider returned an unexpected response shape."


class AdapterRecordValidationError(IngestionError):
    error_code = "adapter_record_validation_failed"
    operator_message = "Provider returned a malformed job record."


class DuplicateIdentityError(IngestionError):
    error_code = "duplicate_provider_identity"
    operator_message = "Provider result contains duplicate job identities."


class ProviderLockError(IngestionError):
    error_code = "provider_locked"
    operator_message = "The selected provider already has a running sync."


class SyncPersistenceError(IngestionError):
    error_code = "sync_persistence_failed"
    operator_message = "Failed to persist sync results."


def sanitize_error(exc: BaseException) -> tuple[str, str]:
    """Return (error_code, operator_message) for any exception."""
    if isinstance(exc, IngestionError):
        return exc.error_code, exc.operator_message
    return "sync_failed", "Sync failed unexpectedly."


__all__ = [
    "AdapterAuthenticationError",
    "AdapterConfigurationError",
    "AdapterRateLimitError",
    "AdapterRecordValidationError",
    "AdapterSchemaError",
    "AdapterTransportError",
    "DuplicateIdentityError",
    "IngestionError",
    "ProviderLockError",
    "SyncPersistenceError",
    "UnknownProviderError",
    "sanitize_error",
]
