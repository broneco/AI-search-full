import os
import asyncio
import logging
from app.storage.db import SessionLocal, init_db
from app.ingestion.loaders.local.py import list_local_files  # Wait, wait, it is loaders/local.py, so it will be app.ingestion.loaders.local
from app.ingestion.loaders.local import list_local_files
from app.ingestion.pipeline import IngestionPipeline

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting local document ingestion script...")
    
    # 1. Initialize tables if they do not exist
    init_db()

    db = SessionLocal()
    pipeline = IngestionPipeline(db)

    # 2. Scan data directory for PDFs
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

    # 3. Process files sequentially in RAG pipeline
    success_count = 0
    import datetime
    for file_path in files:
        file_name = os.path.basename(file_path)
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Formulate realistic corporate security ACLs, freshness statuses and creation dates based on PDF filenames
            if "organizacni" in file_name.lower() or "150" in file_name.lower():
                # S-10.150 Organizační řád (Public)
                security_acl = {"allowed_groups": ["Management", "HR", "Finance", "User"]}
                metadata = {
                    "freshness_status": "archived",
                    "created_at": datetime.datetime(2026, 1, 10, 9, 0, 0),
                    "department": "Management",
                    "year": 2026,
                }
            elif "podpisovy" in file_name.lower() or "160" in file_name.lower():
                # S-10.160 Podpisový řád (Management & HR only)
                security_acl = {"allowed_groups": ["Management", "HR"]}
                metadata = {
                    "freshness_status": "current",
                    "created_at": datetime.datetime(2026, 2, 15, 10, 0, 0),
                    "department": "HR",
                    "year": 2026,
                }
            elif "whistleblowing" in file_name.lower() or "170" in file_name.lower():
                # S-10.170 Whistleblowing (Public)
                security_acl = {"allowed_groups": ["Management", "HR", "Finance", "User"]}
                metadata = {
                    "freshness_status": "current",
                    "created_at": datetime.datetime(2026, 3, 1, 11, 0, 0),
                    "department": "HR",
                    "year": 2026,
                }
            elif "obchod" in file_name.lower() or "marketing" in file_name.lower() or "300" in file_name.lower():
                # S-10.300 Obchod a Marketing (Management & Finance only)
                security_acl = {"allowed_groups": ["Management", "Finance"]}
                metadata = {
                    "freshness_status": "current",
                    "created_at": datetime.datetime(2026, 4, 20, 13, 0, 0),
                    "department": "Finance",
                    "year": 2026,
                }
            elif "projektovy" in file_name.lower() or "310" in file_name.lower():
                # S-10.310 Projektový management (Management & User)
                security_acl = {"allowed_groups": ["Management", "User"]}
                metadata = {
                    "freshness_status": "current",
                    "created_at": datetime.datetime(2026, 5, 12, 14, 0, 0),
                    "department": "Management",
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
    logger.info(f"Ingestion complete. Discovered: {len(files)}, successfully processed: {success_count}.")


if __name__ == "__main__":
    asyncio.run(main())
