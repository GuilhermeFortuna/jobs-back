import json
from functools import lru_cache

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @field_validator("provider_config_json", mode="before")
    @classmethod
    def _default_provider_config_json(cls, value: object) -> str:
        if value is None or value == "":
            return "{}"
        return str(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def provider_config(self) -> dict[str, dict[str, str]]:
        parsed = json.loads(self.provider_config_json)
        if not isinstance(parsed, dict):
            msg = "PROVIDER_CONFIG_JSON must be a JSON object"
            raise ValueError(msg)
        result: dict[str, dict[str, str]] = {}
        for key, item in parsed.items():
            if not isinstance(key, str) or not isinstance(item, dict):
                msg = "PROVIDER_CONFIG_JSON must map provider keys to objects"
                raise ValueError(msg)
            result[key] = {str(k): str(v) for k, v in item.items()}
        return result

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins_csv.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
