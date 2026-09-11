"""Pydantic schemas for Authentication and User management."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserCreateRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: str = Field("viewer", description="admin, analyst, viewer")


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime.datetime
    last_login: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
