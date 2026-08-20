import datetime
import json
import uuid
from typing import List, Optional
from sqlalchemy import ForeignKey, String, DateTime, Integer, Date, JSON, Uuid, Text
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
    title: Mapped[str] = mapped_column(String(512), nullable=False)
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


class DBChunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(255), default="dolphin", index=True, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
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
    groups: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
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
    title: Mapped[str] = mapped_column(String(512), default="Nová konverzace", nullable=False)
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
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    thread: Mapped["DBChatThread"] = relationship("DBChatThread", back_populates="messages")
