import os
import asyncio
import logging
from app.storage.db import SessionLocal, init_db, clear_db
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
    
    # 1. Wipe database schemas and drop tables
    try:
        clear_db()
    except Exception as e:
        logger.warning(f"Drop tables failed (might be clean state): {e}")

    # 2. Re-create tables and extensions
    init_db()

    db = SessionLocal()
    pipeline = IngestionPipeline(db)

    # 3. Scan data directory for PDFs
    data_dir = os.path.abspath("data")
    if not os.path.exists(data_dir):
        logger.info(f"Creating local directory {data_dir}. Place your PDFs here!")
        os.makedirs(data_dir, exist_ok=True)
        db.close()
        return

    logger.info(f"Scanning directory: {data_dir}")
    files = list_local_files(data_dir, extensions=[".pdf", ".txt"])

    if not files:
        logger.info("No matching PDF or TXT files found in the data/ directory.")
        db.close()
        return

    # 4. Process files sequentially in RAG pipeline
    success_count = 0
    import datetime
    for file_path in files:
        file_name = os.path.basename(file_path)
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Formulate realistic corporate security ACLs, freshness statuses and creation dates based on PDF filenames
            if "registr_smluv" in file_name.lower():
                # R_399_registr_smluv
                security_acl = {"allowed_groups": ["Management", "HR"]}
                metadata = {
                    "freshness_status": "current",
                    "created_at": datetime.datetime(2026, 2, 15, 12, 0, 0),
                    "department": "HR",
                    "year": 2026,
                }
            elif "pokusna_zvirata" in file_name.lower():
                # R_402_pokusna_zvirata_ZF
                security_acl = {"allowed_groups": ["Management", "HR", "User"]} # public
                metadata = {
                    "freshness_status": "archived",
                    "created_at": datetime.datetime(2024, 5, 10, 10, 0, 0),
                    "department": "User",
                    "year": 2024,
                }
            elif "evidence_prac_doby" in file_name.lower():
                # R_407_evidence_prac_doby_rektorat
                security_acl = {"allowed_groups": ["Management", "HR"]}
                metadata = {
                    "freshness_status": "current",
                    "created_at": datetime.datetime(2025, 8, 20, 9, 30, 0),
                    "department": "HR",
                    "year": 2025,
                }
            elif "tvorba_rozpoctu" in file_name.lower():
                # R_409_tvorba_rozpoctu_JU
                security_acl = {"allowed_groups": ["Management", "Finance"]}
                metadata = {
                    "freshness_status": "current",
                    "created_at": datetime.datetime(2026, 4, 10, 14, 0, 0),
                    "department": "Finance",
                    "year": 2026,
                }
            else:
                # Default fallback
                security_acl = {"allowed_groups": ["Management", "User"]}
                metadata = {
                    "freshness_status": "current",
                    "created_at": datetime.datetime.utcnow(),
                    "department": "Public",
                    "year": 2026,
                }

            await pipeline.ingest_file(
                file_path=file_path,
                document_type="policy" if "policy" in file_path.lower() else "document",
                security_acl=security_acl,
                metadata_json=metadata,
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")

    db.close()
    logger.info(f"Full refresh ingestion complete. Discovered: {len(files)}, successfully processed: {success_count}.")


if __name__ == "__main__":
    asyncio.run(main())
