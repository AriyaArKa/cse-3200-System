"""Pydantic schemas for auth and jobs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


class OCRJobResponse(BaseModel):
    job_id: str
    document_id: str
    doc_id: str
    status: str
    celery_task_id: str | None = None

