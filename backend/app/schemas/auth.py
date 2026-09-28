"""Strict transport schemas for the public authentication API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class StrictAuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegistrationRequest(StrictAuthModel):
    email: str = Field(min_length=3, max_length=320, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=12, max_length=1024)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be empty")
        return normalized


class EmailRequest(StrictAuthModel):
    email: str = Field(min_length=3, max_length=320, pattern=EMAIL_PATTERN)


class TokenRequest(StrictAuthModel):
    token: str = Field(min_length=43, max_length=128)


class LoginRequest(StrictAuthModel):
    email: str = Field(min_length=3, max_length=320, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=1024)


class PasswordResetRequest(TokenRequest):
    new_password: str = Field(min_length=12, max_length=1024)


class AuthMessage(BaseModel):
    message: str


class CurrentUser(BaseModel):
    id: UUID
    email: str
    role: Literal["user", "admin"]
    display_name: str


class SessionResponse(BaseModel):
    user: CurrentUser
    csrf_token: str
    expires_at: datetime
