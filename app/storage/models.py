import datetime
import json
import uuid
from typing import List, Optional
from sqlalchemy import ForeignKey, String, Unicode, UnicodeText, DateTime, Integer, Date, JSON, Uuid, Text, Index, Boolean
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from app.core.config import settings


class UniversalVector(TypeDecorator):
    """Stores vector as pgvector on PostgreSQL and JSON string array on Azure SQL / SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(1536))
            except ImportError:
                return dialect.type_descriptor(Text())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name != "postgresql" and isinstance(value, list):
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name != "postgresql" and isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value


class Base(DeclarativeBase):
    pass


class DBDocument(Base):
    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(255), default=lambda: settings.TENANT_ID, index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(255), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(512).with_variant(Unicode(512), "mssql"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(32), default="en")
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    valid_from: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(64), default="current")
    security_acl: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, name="metadata"
    )

    chunks: Mapped[List["DBChunk"]] = relationship(
        "DBChunk", back_populates="document", cascade="all, delete-orphan"
    )
    acl_grants: Mapped[List["DBDocumentACL"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class DBEmbeddingProfile(Base):
    __tablename__ = "embedding_profiles"
    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)


class DBSearchIndex(Base):
    __tablename__ = "search_indexes"
    index_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(Unicode(255), nullable=False, index=True)
    corpus_id: Mapped[str] = mapped_column(String(64), nullable=False, default="tenant-chunks-v1")
    profile_id: Mapped[str] = mapped_column(ForeignKey("embedding_profiles.profile_id"), nullable=False)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    storage_kind: Mapped[str] = mapped_column(String(32), nullable=False)


class DBActiveSearchIndex(Base):
    __tablename__ = "active_search_indexes"
    tenant_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    index_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_indexes.index_id"), nullable=False)


class DBChunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(255), default=lambda: settings.TENANT_ID, index=True, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text().with_variant(UnicodeText(), "mssql"), nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        UniversalVector(), nullable=True
    )
    language: Mapped[str] = mapped_column(String(32), default="en")
    section_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    valid_from: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(64), default="current")
    security_acl: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, name="metadata"
    )

    document: Mapped["DBDocument"] = relationship("DBDocument", back_populates="chunks")
    acl_grants: Mapped[List["DBChunkACL"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


ACL_GROUP_TYPE = Unicode(255).with_variant(
    Unicode(255, collation="Latin1_General_100_BIN2"), "mssql"
)


class DBDocumentACL(Base):
    __tablename__ = "document_acl_grants"
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id", ondelete="CASCADE"), primary_key=True
    )
    group_name: Mapped[str] = mapped_column(ACL_GROUP_TYPE, primary_key=True)
    __table_args__ = (Index("ix_document_acl_group", "group_name", "document_id"),)


class DBChunkACL(Base):
    __tablename__ = "chunk_acl_grants"
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chunks.chunk_id", ondelete="CASCADE"), primary_key=True
    )
    group_name: Mapped[str] = mapped_column(ACL_GROUP_TYPE, primary_key=True)
    __table_args__ = (Index("ix_chunk_acl_group", "group_name", "chunk_id"),)


class DBUser(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(255), default="dolphin", index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), default="User")
    groups: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    threads: Mapped[List["DBChatThread"]] = relationship(
        "DBChatThread", back_populates="user", cascade="all, delete-orphan"
    )


class DBChatThread(Base):
    __tablename__ = "chat_threads"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(255), default=lambda: settings.TENANT_ID, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512).with_variant(Unicode(512), "mssql"), default="Nová konverzace", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    user: Mapped["DBUser"] = relationship("DBUser", back_populates="threads")
    messages: Mapped[List["DBChatMessage"]] = relationship(
        "DBChatMessage", back_populates="thread", cascade="all, delete-orphan", order_by="DBChatMessage.created_at.asc()"
    )


class DBChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(255), default="dolphin", index=True, nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("chat_threads.thread_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text().with_variant(UnicodeText(), "mssql"), nullable=False)
    sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    thread: Mapped["DBChatThread"] = relationship("DBChatThread", back_populates="messages")


class DBTenantSetting(Base):
    """Durable mutable configuration; bundled tenant JSON remains a default only."""
    __tablename__ = "tenant_settings"
    tenant_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow,
                                                       onupdate=datetime.datetime.utcnow, nullable=False)
    __mapper_args__ = {"version_id_col": revision}


class DBModelAccess(Base):
    """Per-tenant overrides; null means all groups, an empty list denies everyone."""
    __tablename__ = "model_access_policies"
    tenant_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    allowed_groups: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class DBTenantModel(Base):
    """Approved immutable local profiles; publication is separate from group ACL."""
    __tablename__ = "tenant_model_registry"
    tenant_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    profile_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    user_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class DBModelRuntimeSettings(Base):
    """Mutable generation limits, separate from approved model/vector identity."""
    __tablename__ = "model_runtime_settings"
    tenant_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    max_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class DBModelDescription(Base):
    """Editable presentation metadata, separate from immutable model/vector identity."""
    __tablename__ = "model_descriptions"
    tenant_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)


# Register transaction-local ACL projection maintenance after all models exist.
from app.storage import acl as _acl  # noqa: E402,F401
