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
    for file_path in files:
        try:
            logger.info(f"Processing file: {file_path}")
            await pipeline.ingest_file(
                file_path=file_path,
                document_type="policy" if "policy" in file_path.lower() else "document",
                security_acl={"allowed_groups": ["HR", "Engineering", "Finance", "Public"]},
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")

    db.close()
    logger.info(f"Full refresh ingestion complete. Discovered: {len(files)}, successfully processed: {success_count}.")


if __name__ == "__main__":
    asyncio.run(main())
