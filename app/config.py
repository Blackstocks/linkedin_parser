from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    linkedin_li_at: str = ""
    linkedin_jsessionid: str = ""
    linkedin_csrf_token: str = ""
    linkedin_extra_cookies: str = ""
    linkedin_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )
    linkedin_extra_headers: str = ""
    linkedin_sdui_client_version: str = "0.2.2045"
    log_level: str = "INFO"
    request_timeout_seconds: float = 30.0
    linkedin_component_id: str = Field(
        default="com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity"
    )

    @field_validator("linkedin_li_at", "linkedin_jsessionid", "linkedin_csrf_token", mode="before")
    @classmethod
    def strip_cookie_quotes(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    def csrf_token(self) -> str:
        if self.linkedin_csrf_token:
            return self.linkedin_csrf_token.strip().strip('"')
        return self.linkedin_jsessionid

    def extra_headers(self) -> dict[str, str]:
        raw = self.linkedin_extra_headers.strip()
        if not raw:
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("LINKEDIN_EXTRA_HEADERS must be a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}

    def has_session(self) -> bool:
        return bool(self.linkedin_li_at and self.linkedin_jsessionid)


@lru_cache
def get_settings() -> Settings:
    return Settings()
