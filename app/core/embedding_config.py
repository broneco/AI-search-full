"""Tenant embedding connections, separate from immutable vector-space identity."""
import json
import re
from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
from app.core.model_config import ModelError
from app.core.tenant_config import resolve_tenant_file_path
from app.providers.embeddings import EmbeddingProfile


class EmbeddingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,99}$")
    provider: Literal["azure_openai", "ollama_embed"]
    # Existing Azure settings retain their original profile fingerprint.
    profile: EmbeddingProfile | None = None
    batch_size: int = Field(8, ge=1, le=32)
    timeout_seconds: int = Field(180, ge=1, le=300)
    max_input_chars: int = Field(12000, ge=1, le=100000)

    @model_validator(mode="after")
    def validate_profile(self):
        if self.provider == "azure_openai":
            if self.profile is not None:
                raise ValueError("Azure profile is defined by the existing Azure settings.")
        elif self.profile is None or self.profile.normalization != "l2" or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", self.profile.model_revision):
            raise ValueError("Ollama requires an explicit L2 profile pinned to its model digest.")
        if self.profile and self.profile.dimensions > 1998:
            raise ValueError("Profile exceeds the supported SQL float32 vector dimension limit.")
        return self

    def space(self) -> EmbeddingProfile:
        if self.profile is not None:
            return self.profile
        return EmbeddingProfile(
            model_id=settings.AZURE_OPENAI_EMBEDDING_MODEL,
            model_revision=settings.AZURE_OPENAI_EMBEDDING_MODEL_REVISION,
            dimensions=settings.AZURE_OPENAI_EMBEDDING_DIMENSIONS,
            query_prefix=settings.AZURE_OPENAI_EMBEDDING_QUERY_PREFIX,
            document_prefix=settings.AZURE_OPENAI_EMBEDDING_DOCUMENT_PREFIX,
        )


class EmbeddingCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    default_profile: str
    profiles: list[EmbeddingEntry]

    @model_validator(mode="after")
    def validate_entries(self):
        ids = [entry.id for entry in self.profiles]
        spaces = [entry.space().profile_id for entry in self.profiles]
        if len(set(ids)) != len(ids) or len(set(spaces)) != len(spaces) or self.default_profile not in ids:
            raise ValueError("Duplicate or missing embedding profile.")
        return self


def load_embedding_catalog(tenant: str) -> EmbeddingCatalog:
    path, _ = resolve_tenant_file_path(tenant, "embedding_config.json")
    try:
        with open(path, encoding="utf-8-sig") as stream:
            return EmbeddingCatalog.model_validate(json.load(stream))
    except (OSError, ValueError, TypeError):
        raise ModelError("embedding_config_invalid", "Konfigurace embeddingových profilů není platná.") from None


def embedding_entry(tenant: str, name: str | None = None, *, space: EmbeddingProfile | None = None, session=None) -> EmbeddingEntry:
    from app.core.local_model_registry import embedding_catalog
    catalog = embedding_catalog(session, tenant) if session is not None else load_embedding_catalog(tenant)
    for entry in catalog.profiles:
        if (space is not None and asdict(entry.space()) == asdict(space)) or (
                space is None and entry.id == (name or catalog.default_profile)):
            return entry
    raise ModelError("embedding_profile_unavailable", "Embeddingový profil indexu není nakonfigurován pro tento tenant.")
