"""Strict, file-level tenant model catalogs. Secrets never belong in this schema."""
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.tenant_config import resolve_tenant_file_path

Purpose = Literal["chat", "summary", "classification"]


class ModelError(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        super().__init__(message)
        self.code, self.status = code, status


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,99}$")
    name: str
    description: dict[Literal["cs", "en"], str]
    location: Literal["local", "cloud"]
    provider: Literal["azure_openai", "ollama_generate"]
    model: str
    connection: Literal["azure_mini", "azure_advanced", "jhu"]
    purposes: list[Purpose]
    enabled: bool = True
    timeout_seconds: int = Field(60, ge=1, le=300)
    max_input_chars: int = Field(60000, ge=1000, le=1000000)
    max_output_tokens: int = Field(4096, ge=128, le=32768)
    reasoning_effort: Literal["none", "low", "medium", "high"] = "none"
    model_digest: str | None = Field(None, pattern=r"^[0-9a-f]{64}$")
    context_tokens: int | None = Field(None, ge=2048, le=8192)

    @model_validator(mode="after")
    def validate_connection(self):
        if (self.provider == "ollama_generate") != (self.connection == "jhu"):
            raise ValueError("Provider and connection disagree.")
        if self.model_digest is not None and (self.provider != "ollama_generate" or self.context_tokens is None):
            raise ValueError("Pinned local models require an explicit context budget.")
        if not self.purposes or set(self.description) != {"cs", "en"}:
            raise ValueError("Purposes and CS/EN descriptions are required.")
        return self


class ModelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    defaults: dict[Purpose, str]
    advanced_chat_model: str
    profiles: list[ModelProfile]

    @model_validator(mode="after")
    def validate_defaults(self):
        profiles = {p.id: p for p in self.profiles}
        if len(profiles) != len(self.profiles) or set(self.defaults) != {"chat", "summary", "classification"}:
            raise ValueError("Duplicate profile or missing default.")
        for purpose, ident in [*self.defaults.items(), ("chat", self.advanced_chat_model)]:
            if ident not in profiles or purpose not in profiles[ident].purposes or not profiles[ident].enabled:
                raise ValueError("Default model is missing, disabled or incompatible.")
        return self


def load_model_catalog(tenant_id: str) -> ModelCatalog:
    path, _ = resolve_tenant_file_path(tenant_id, "model_config.json")
    try:
        with open(path, encoding="utf-8-sig") as stream:
            return ModelCatalog.model_validate(json.load(stream))
    except (OSError, ValueError, TypeError):
        raise ModelError("model_config_invalid", "Konfigurace modelů není platná. Kontaktujte správce.") from None
