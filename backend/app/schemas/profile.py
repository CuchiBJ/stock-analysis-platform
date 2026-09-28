"""Allow-listed request and response schemas for the current-user profile."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not 1 <= len(normalized) <= 80:
            raise ValueError("display_name must contain between 1 and 80 characters")
        return normalized


class ProfileResponse(BaseModel):
    user_id: UUID
    email: str
    role: Literal["user", "admin"]
    display_name: str
    created_at: datetime
    updated_at: datetime
