from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Serialized JSON size (bytes) of one retained JobResult including its raw
# provider_payload, measured from the recorded provider fixtures and asserted in
# tests/test_search_retention.py. Fixture descriptions are trimmed, so this is a
# floor: deployments seeing long descriptions should set SEARCH_MAX_ITEMS
# explicitly rather than relying on the derived default.
OBSERVED_ITEM_BYTES = 600
BASELINE_MAX_ITEMS = 100_000
BASELINE_MAX_STATES = 200


@dataclass(frozen=True)
class ProviderConfigEntry:
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+psycopg://jobs:jobs@localhost:5432/jobs",
        alias="DATABASE_URL",
    )
    cors_origins_csv: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
    )
    provider_config_json: str = Field(default="{}", alias="PROVIDER_CONFIG_JSON")
    search_state_ttl_minutes: int = Field(default=60, alias="SEARCH_STATE_TTL_MINUTES")
    search_max_states: int = Field(default=200, alias="SEARCH_MAX_STATES")
    search_max_items: int = Field(default=100_000, alias="SEARCH_MAX_ITEMS")
    search_eviction_interval_seconds: int = Field(
        default=60,
        alias="SEARCH_EVICTION_INTERVAL_SECONDS",
    )
    himalayas_concurrency: int = Field(default=12, alias="HIMALAYAS_CONCURRENCY")
    himalayas_timeout_seconds: float = Field(
        default=20.0,
        alias="HIMALAYAS_TIMEOUT_SECONDS",
    )
    adzuna_app_id: str = Field(default="", alias="ADZUNA_APP_ID")
    adzuna_app_key: str = Field(default="", alias="ADZUNA_APP_KEY")
    adzuna_default_country: str = Field(default="gb", alias="ADZUNA_DEFAULT_COUNTRY")
    adzuna_concurrency: int = Field(default=8, alias="ADZUNA_CONCURRENCY")
    adzuna_timeout_seconds: float = Field(
        default=20.0,
        alias="ADZUNA_TIMEOUT_SECONDS",
    )

    @field_validator("provider_config_json", mode="before")
    @classmethod
    def _default_provider_config_json(cls, value: object) -> str:
        if value is None or value == "":
            return "{}"
        return str(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def provider_config(self) -> dict[str, ProviderConfigEntry]:
        parsed = json.loads(self.provider_config_json)
        if not isinstance(parsed, dict):
            msg = "PROVIDER_CONFIG_JSON must be a JSON object"
            raise ValueError(msg)
        result: dict[str, ProviderConfigEntry] = {}
        for key, item in parsed.items():
            if not isinstance(key, str) or not isinstance(item, dict):
                msg = f"PROVIDER_CONFIG_JSON entry {key!r} must be an object"
                raise ValueError(msg)
            enabled = item.get("enabled", True)
            if not isinstance(enabled, bool):
                msg = f"PROVIDER_CONFIG_JSON entry {key!r} enabled must be a boolean"
                raise ValueError(msg)
            options = item.get("options", {})
            if not isinstance(options, dict):
                msg = f"PROVIDER_CONFIG_JSON entry {key!r} options must be an object"
                raise ValueError(msg)
            result[key] = ProviderConfigEntry(
                enabled=enabled,
                options={str(k): v for k, v in options.items()},
            )
        return result

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins_csv.split(",")
            if origin.strip()
        ]

    def effective_search_max_items(self, enabled_provider_count: int) -> int:
        """Scale the global item budget with fan-in volume.

        Fan-in multiplies the items one index holds by roughly the enabled
        provider count. Inheriting the single-provider budget would therefore
        evict warm indexes that are still in use purely because more providers
        were enabled, which JE-007 forbids. An explicit SEARCH_MAX_ITEMS always
        wins, so a memory-constrained deployment can cap this.
        """
        if self.search_max_items != BASELINE_MAX_ITEMS:
            return self.search_max_items
        return BASELINE_MAX_ITEMS * max(1, enabled_provider_count)

    def effective_search_max_states(self, enabled_provider_count: int) -> int:
        """Fan-in adds items per state, not additional states.

        The state budget is therefore unchanged by the enabled provider count;
        the item budget above absorbs fan-in volume.
        """
        del enabled_provider_count
        return self.search_max_states


@lru_cache
def get_settings() -> Settings:
    return Settings()
