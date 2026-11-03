"""Resolve only the exact stored source of an already authorized document."""
import asyncio
from contextlib import contextmanager
import hashlib
from pathlib import Path, PurePosixPath
import tempfile
from collections.abc import Iterator
from typing import Protocol

from app.core.config import settings
from app.core.model_config import ModelError
from app.providers.blob_storage import BlobStorageProvider
from app.retrieval.access import safe_data_path


class SourceReference(Protocol):
    source_uri: str
    checksum: str | None


@contextmanager
def document_source(document: SourceReference) -> Iterator[str]:
    """Synchronous worker boundary; no basename search, URL fetch or storage fallback."""
    uri = document.source_uri
    if uri.startswith("azure://"):
        parts = uri[8:].split("/", 1)
        container = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
        if len(parts) != 2 or parts[0] != container:
            raise ModelError("document_source_invalid", "Zdroj dokumentu má neplatný kontejner.", 409)
        name = parts[1]
        if (not name or name.startswith("/") or "\\" in name or ":" in name
                or any(part in {"", ".", ".."} for part in name.split("/"))):
            raise ModelError("document_source_invalid", "Zdroj dokumentu má neplatnou cestu.", 409)
        provider = BlobStorageProvider()
        if not provider.is_configured():
            raise ModelError("document_source_unavailable", "Úložiště originálů není dostupné.", 503)
        try:
            data = asyncio.run(provider.download_blob(container, name))
        except Exception:
            raise ModelError("document_source_unavailable", "Originál dokumentu se nepodařilo načíst z úložiště.", 503) from None
        if document.checksum and hashlib.sha256(data).hexdigest() != document.checksum:
            raise ModelError("document_source_changed", "Originál se změnil oproti evidovanému dokumentu.", 409)
        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in {".pdf", ".txt"}:
            raise ModelError("document_source_unsupported", "Náhled podporuje originály PDF a TXT.", 422)
        with tempfile.TemporaryDirectory(prefix="ai-search-source-") as directory:
            path = Path(directory) / ("source" + suffix)
            path.write_bytes(data)
            yield str(path)
        return
    name = uri[7:] if uri.startswith("file://") else uri
    if "://" in name:
        raise ModelError("document_source_invalid", "Nepodporovaný typ zdroje dokumentu.", 409)
    path = safe_data_path(str(Path("data") / name))
    if path is None:
        raise ModelError("document_source_invalid", "Zdroj je mimo adresář dokumentů.", 404)
    if not Path(path).is_file():
        raise ModelError("document_source_missing", "Přesný originál dokumentu není dostupný.", 404)
    if document.checksum:
        with Path(path).open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != document.checksum:
            raise ModelError("document_source_changed", "Originál se změnil oproti evidovanému dokumentu.", 409)
    yield path
