"""Canonical HTTP contracts; OpenAPI is exported from these models."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class Login(Input):
    login: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: SecretStr = Field(min_length=12, max_length=256)


class Register(Login):
    confirmation: SecretStr = Field(min_length=12, max_length=256)


class Code(Input):
    code: str = Field(pattern=r"^\d{8}$")


class Recovery(Input):
    code: str = Field(min_length=16, max_length=64)


class ProjectInput(Input):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name is required")
        return value.strip()


class Project(ProjectInput):
    id: UUID


class Connection(Input):
    host: str = Field(min_length=1, max_length=253, pattern=r"^[a-zA-Z0-9.:-]+$")
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    method: Literal["password", "key", "certificate"]
    password: SecretStr = SecretStr("")
    private_key: SecretStr = SecretStr("")
    certificate: SecretStr = SecretStr("")
    passphrase: SecretStr = SecretStr("")
    fingerprint: str = Field(default="", max_length=128)


class Envelope(Input):
    jwe: str = Field(min_length=100, max_length=60000)


class Probe(Input):
    host: str = Field(min_length=1, max_length=253, pattern=r"^[a-zA-Z0-9.:-]+$")
    port: int = Field(default=22, ge=1, le=65535)


class CheckRequest(Envelope):
    server_id: UUID | None = None


class CheckResult(BaseModel):
    proof: str
    fingerprint: str
    expires_at: float


class Fingerprint(BaseModel):
    fingerprint: str


class ServerInput(Input):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["VPS", "VM"]
    proof: str | None = Field(default=None, max_length=128)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        return ProjectInput.nonblank(value)


class Server(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    kind: Literal["VPS", "VM"]
    host: str
    port: int
    username: str
    method: Literal["password", "key", "certificate"]
    fingerprint: str
    checked_at: float


class AuthState(BaseModel):
    state: Literal["enrollment", "otp", "authenticated"]
    expires_at: float | None = None
    telegram_url: str | None = None
    recovery_codes: list[str] = Field(default_factory=list)


class Me(BaseModel):
    id: UUID
    login: str


class EncryptionKey(BaseModel):
    key: dict[str, str]
    nonce: str
    expires_at: float
