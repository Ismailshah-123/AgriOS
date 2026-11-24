import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.identity.models import Locale, UserRole

# NIST SP 800-63B style: length matters, composition rules do not.
Password = Annotated[str, Field(min_length=10, max_length=128)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def normalise_email(value: str) -> str:
    return value.strip().lower()


class _EmailModel(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def _normalise(cls, v: object) -> object:
        return normalise_email(v) if isinstance(v, str) else v


class RegisterRequest(_EmailModel):
    model_config = ConfigDict(extra="forbid")
    password: Password
    full_name: FullName
    locale: Locale = Locale.EN


class LoginRequest(_EmailModel):
    model_config = ConfigDict(extra="forbid")
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    locale: Locale
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth2 scheme name, not a secret
    expires_in: int
    user: UserOut


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: FullName | None = None
    locale: Locale | None = None


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Password
