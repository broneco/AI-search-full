"""Tenant-scoped refresh without deleting the corpus before model calls succeed."""
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.tenant_identity import tenant_config_name
from app.ingestion.loaders.local import list_local_files
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.tagger import MetadataTagger
from app.retrieval.filters import exact_value
from app.storage.db import SessionLocal
from app.storage.models import DBDocument, DBChunk


def source_key(value: str) -> str:
    if value.startswith("file://"):
        return value[7:]
    if value.startswith("azure://"):
        return value.split("/", 3)[-1]
    parts = str(Path(value).resolve()).replace("\\", "/").split("/data/")
    return parts[-1] if len(parts) > 1 else Path(value).name


def check_tenant(tenant_id: str) -> None:
    if not tenant_id or tenant_id != settings.TENANT_ID:
        raise ValueError("Refresh tenant must exactly match the configured TENANT_ID.")


def refresh_files(tenant_id: str, data_dir: str | None = None) -> list[str]:
    """Validate a complete source set before creating sessions or calling models."""
    check_tenant(tenant_id)
    if data_dir is not None:
        directory = Path(data_dir).resolve(strict=True)
        if not directory.is_dir():
            raise ValueError("Refresh source must be a directory.")
    else:
        base = tenant_config_name(tenant_id)
        candidates = [Path(parent) / name for parent in ("data", "data - full backup", "data-full backup")
                      for name in dict.fromkeys((tenant_id, base))]
        directory = next((path.resolve() for path in candidates if path.is_dir()), None)
        if directory is None:
            raise ValueError("No tenant source directory; specify --data-dir explicitly. No documents were removed.")
    files = sorted(set(list_local_files(str(directory), extensions=[".pdf", ".txt"])))
    if not files:
        raise ValueError("Refresh source contains no PDF/TXT documents. No documents were removed.")
    source_keys = set()
    for name in files:
        path = Path(name).resolve(strict=True)
        if not path.is_relative_to(directory):
            raise ValueError("Refresh source contains a file outside its directory.")
        with path.open("rb") as stream:
            stream.read(1)
        key = source_key(str(path))
        if key in source_keys:
            raise ValueError("Source paths collide in ingestion; use distinct filenames or a data/ tenant folder.")
        source_keys.add(key)
    return files


async def refresh_documents(tenant_id: str, files: list[str], progress: dict | None = None, *, model_selection=None, principal=None) -> None:
    """Commit replacements per document; prune initial stale IDs only after full success.

    A failed run may retain successful replacements, but never prunes the remaining
    corpus. Newly uploaded documents and concurrently changed stale rows are protected.
    """
    check_tenant(tenant_id)
    if not files:
        raise ValueError("A refresh requires nonempty validated sources.")
    progress = progress if progress is not None else {}
    with SessionLocal() as db:
        dialect = db.bind.dialect.name
        original = list(db.execute(select(
            DBDocument.document_id, DBDocument.checksum, DBDocument.updated_at, DBDocument.source_uri
        ).where(exact_value(DBDocument.tenant_id, tenant_id, dialect))).all())
        from app.core.model_selection import model_provider
        selection = model_selection or {}
        classifier = model_provider(db, tenant_id, "classification", selection.get("classification_model_id"), principal) if model_selection is not None else None
        tagger = MetadataTagger(db_session=db, llm_provider=classifier) if classifier else MetadataTagger(db_session=db)
        config = await tagger.load_config()
        categories = {item["key"]: item for item in config.get("categories", [])}
        progress.update(phase="analyzing", total_files=len(files), processed_files=0)
        analyzed = []
        for position, name in enumerate(files):
            progress.update(current_file=Path(name).name, processed_files=position)
            suggestion = await tagger.analyze_file(name)
            category = categories.get(suggestion["suggested_category"])
            if category is None or not isinstance(category.get("allowed_groups"), list):
                raise ValueError("Classification returned an unknown category or invalid ACL; refresh stopped.")
            try:
                date = datetime.strptime(suggestion.get("suggested_date", ""), "%Y-%m-%d")
            except (TypeError, ValueError):
                date = datetime.now()
            analyzed.append((date, name, suggestion, category))
        summary = model_provider(db, tenant_id, "summary", selection.get("summary_model_id"), principal) if model_selection is not None else None
        pipeline = IngestionPipeline(db, summary_provider=summary, principal=principal) if summary else IngestionPipeline(db)
        kept_ids = set()
        replacements = {}
        relationships = []
        progress.update(phase="ingesting", processed_files=0)
        for position, (date, name, suggestion, category) in enumerate(sorted(analyzed, key=lambda item: item[0])):
            progress.update(current_file=Path(name).name, processed_files=position)
            metadata = {"department": category["key"], "year": date.year,
                        "created_at": date.isoformat(), "freshness_status": "current",
                        "relationship_type": (suggestion.get("relationship") or {}).get("relationship_type", "none")}
            if classifier:
                metadata["classification_model_id"] = classifier.profile.id
            folder = Path(source_key(name)).parent.as_posix()
            if folder != ".":
                metadata.update(source_folder=folder, **{"Zdroj dat": folder})
            doc = await pipeline.ingest_file(name, document_type="document",
                security_acl={"allowed_groups": category["allowed_groups"]}, metadata_json=metadata,
                language=suggestion.get("suggested_language", "cs"), force_reindex=True)
            if doc.tenant_id != tenant_id:
                db.rollback()
                raise ValueError("Ingestion returned a document from another tenant.")
            doc.title = suggestion["title"]
            doc.created_at = date
            db.commit()
            kept_ids.add(doc.document_id)
            for old_id, _, _, uri in original:
                if source_key(uri) == source_key(name):
                    replacements[old_id] = doc.document_id
            relationships.append((doc.document_id, suggestion.get("relationship") or {}))
        # Resolve old model-provided IDs to their new versions, only inside this tenant.
        for doc_id, relation in relationships:
            kind, target = relation.get("relationship_type"), relation.get("target_document_id")
            if kind not in {"replaces", "modifies"} or not target:
                continue
            try:
                target_id = UUID(str(target))
            except ValueError:
                raise ValueError("Invalid relationship target; cleanup cancelled.") from None
            target_id = replacements.get(target_id, target_id)
            target_doc = db.get(DBDocument, target_id)
            if target_doc is None or target_doc.tenant_id != tenant_id or target_id == doc_id:
                raise ValueError("Relationship target is unavailable in this tenant; cleanup cancelled.")
            doc = db.get(DBDocument, doc_id)
            key = "replaces" if kind == "replaces" else "modifies"
            doc.metadata_json = {**(doc.metadata_json or {}), key+"_document_id": str(target_id),
                                 key+"_document_title": target_doc.title}
            kept_ids.add(target_id)
            if kind == "replaces":
                target_doc.freshness_status = "archived"
                target_doc.metadata_json = {**(target_doc.metadata_json or {}),
                    "replaced_by_document_id": str(doc_id), "replaced_by_document_title": doc.title}
                for chunk in db.scalars(select(DBChunk).where(DBChunk.document_id == target_id,
                    exact_value(DBChunk.tenant_id, tenant_id, dialect))):
                    chunk.freshness_status = "archived"
        # Only rows present at the start can be stale. Never delete concurrent uploads.
        stale = []
        for ident, checksum, updated_at, _ in original:
            if ident in kept_ids:
                continue
            doc = db.get(DBDocument, ident, populate_existing=True)
            if doc is None:
                continue  # Replaced transactionally by the pipeline.
            if doc.tenant_id != tenant_id or doc.checksum != checksum or doc.updated_at != updated_at:
                raise ValueError("Corpus changed during refresh; stale cleanup cancelled.")
            stale.append((ident, checksum, updated_at))
        for ident, checksum, updated_at in stale:
            changed = db.execute(delete(DBDocument).where(
                DBDocument.document_id == ident,
                exact_value(DBDocument.tenant_id, tenant_id, dialect),
                DBDocument.checksum == checksum, DBDocument.updated_at == updated_at,
            ).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                db.rollback()
                raise ValueError("Concurrent document change; stale cleanup rolled back.")
        db.commit()
        progress.update(processed_files=len(files), current_file=None, phase=None)
