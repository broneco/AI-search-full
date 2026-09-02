import os
import asyncio
import logging
from app.storage.db import SessionLocal, init_db, clear_document_data
from app.ingestion.loaders.local import list_local_files
from app.ingestion.pipeline import IngestionPipeline

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Full-Refresh Document Ingestion script...")

    import argparse
    parser = argparse.ArgumentParser(description="Full-Refresh Document Ingestion script.")
    parser.add_argument("--tenant", type=str, default=None, help="Tenant ID (e.g. dolphin, alzbeta, jhu)")
    parser.add_argument("--data-dir", type=str, default=None, help="Explicit directory path to scan for documents")
    args, _ = parser.parse_known_args()

    from app.core.config import settings
    raw_tenant = args.tenant or os.getenv("TENANT_ID") or settings.TENANT_ID or "dolphin"
    tenant_id = raw_tenant.lower().split("-")[0]

    # 1. Clear document chunks and metadata ONLY for the target tenant
    try:
        clear_document_data(tenant_id=tenant_id)
    except Exception as e:
        logger.warning(f"Clear document data failed: {e}")

    # 2. Re-create tables and extensions
    init_db()

    db = SessionLocal()
    pipeline = IngestionPipeline(db)
    
    # Imports for dynamic metadata analysis
    from app.ingestion.tagger import MetadataTagger
    from app.storage.models import DBDocument, DBChunk
    import uuid
    import datetime

    tagger = MetadataTagger(db_session=db)
    config = await tagger.load_config()

    import argparse
    parser = argparse.ArgumentParser(description="Full-Refresh Document Ingestion script.")
    parser.add_argument("--tenant", type=str, default=None, help="Tenant ID (e.g. dolphin, alzbeta, jhu)")
    parser.add_argument("--data-dir", type=str, default=None, help="Explicit directory path to scan for documents")
    args, _ = parser.parse_known_args()

    from app.core.config import settings
    raw_tenant = args.tenant or os.getenv("TENANT_ID") or settings.TENANT_ID or "dolphin"
    tenant_id = raw_tenant.lower().split("-")[0]

    # 3. Scan data directory for PDFs/TXTs
    data_dir = None
    if args.data_dir and os.path.exists(args.data_dir):
        data_dir = os.path.abspath(args.data_dir)
    else:
        candidates = [
            os.path.abspath(os.path.join("data - full backup", tenant_id)),
            os.path.abspath(os.path.join("data-full backup", tenant_id)),
            os.path.abspath(os.path.join("data", tenant_id)),
            os.path.abspath("data"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                data_dir = candidate
                break

    if not data_dir or not os.path.exists(data_dir):
        logger.warning(f"No valid data directory found for tenant '{tenant_id}'. Ingestion skipped.")
        db.close()
        return

    logger.info(f"Scanning document directory for tenant '{tenant_id}': {data_dir}")
    files = list_local_files(data_dir, extensions=[".pdf", ".txt"])

    if not files:
        logger.info(f"No matching PDF or TXT files found in '{data_dir}'. Ingestion skipped.")
        db.close()
        return

    # 4. Phase A: Analyze metadata for all files to sort them chronologically
    logger.info("Running dynamic MetadataTagger analysis phase...")
    analyzed_docs = []
    for file_path in files:
        try:
            suggestions = await tagger.analyze_file(file_path)
            analyzed_docs.append({
                "file_path": file_path,
                "suggestions": suggestions
            })
        except Exception as e:
            logger.error(f"Failed to analyze file {file_path}: {e}")

    def get_sort_date(item):
        date_str = item["suggestions"].get("suggested_date")
        try:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return datetime.datetime.min

    analyzed_docs.sort(key=get_sort_date)

    # 5. Phase B: Process files sequentially in chronological order
    success_count = 0
    for item in analyzed_docs:
        file_path = item["file_path"]
        sug = item["suggestions"]
        title = sug["title"]
        category_key = sug["suggested_category"]
        date_str = sug["suggested_date"]
        rel = sug["relationship"]

        try:
            logger.info(f"Ingesting file: {file_path} (Classified category key: {category_key})")
            
            # Resolve allowed groups from dynamic config
            category_item = None
            for cat in config.get("categories", []):
                if cat.get("key") == category_key:
                    category_item = cat
                    break

            if not category_item:
                allowed_groups = ["Management", "HR", "Finance", "User"]
            else:
                allowed_groups = category_item.get("allowed_groups", ["Management", "HR", "Finance", "User"])

            security_acl = {"allowed_groups": allowed_groups}

            try:
                release_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                release_date = datetime.datetime.utcnow()

            # Metadata dict
            metadata = {
                "department": category_key,
                "year": release_date.year,
                "created_at": release_date.isoformat(),
                "freshness_status": "current",
                "relationship_type": rel.get("relationship_type", "none"),
            }

            # Calculate source folder relative to data_dir
            rel_dir = os.path.relpath(os.path.dirname(file_path), data_dir).replace("\\", "/")
            if rel_dir and rel_dir != ".":
                metadata["source_folder"] = rel_dir
                metadata["Zdroj dat"] = rel_dir

            # Check if replaces target
            rel_type = rel.get("relationship_type", "none")
            target_doc = None
            if rel_type == "replaces" and rel.get("target_document_id"):
                try:
                    target_uuid = uuid.UUID(rel.get("target_document_id"))
                    target_doc = db.query(DBDocument).filter(DBDocument.document_id == target_uuid).first()
                    if target_doc:
                        logger.info(f"Archiving replaced document: {target_doc.title}")
                        target_doc.freshness_status = "archived"
                        if not target_doc.metadata_json:
                            target_doc.metadata_json = {}
                        target_doc.metadata_json["replaced_by_document_title"] = title
                        
                        db.query(DBChunk).filter(DBChunk.document_id == target_uuid).update(
                            {"freshness_status": "archived"}
                        )
                        metadata["replaces_document_id"] = str(target_uuid)
                        metadata["replaces_document_title"] = target_doc.title
                        db.flush()
                except Exception as ex:
                    logger.error(f"Archival relationship error: {ex}")

            elif rel_type == "modifies" and rel.get("target_document_id"):
                metadata["modifies_document_id"] = rel.get("target_document_id")
                metadata["modifies_document_title"] = rel.get("target_document_title")

            doc = await pipeline.ingest_file(
                file_path=file_path,
                document_type="policy" if "policy" in file_path.lower() else "document",
                security_acl=security_acl,
                metadata_json=metadata,
                language=sug.get("suggested_language", "cs"),
            )
            doc.title = title
            doc.created_at = release_date
            doc.tenant_id = tenant_id
            db.query(DBChunk).filter(DBChunk.document_id == doc.document_id).update({"tenant_id": tenant_id})

            if target_doc:
                target_doc.metadata_json["replaced_by_document_id"] = str(doc.document_id)
                db.add(target_doc)

            db.commit()
            success_count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to ingest file {file_path}: {e}")

    db.close()
    logger.info(f"Full refresh ingestion complete. Discovered: {len(files)}, successfully processed: {success_count}.")



if __name__ == "__main__":
    asyncio.run(main())
