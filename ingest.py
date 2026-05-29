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
    logger.info(f"Ingestion complete. Discovered: {len(files)}, successfully processed: {success_count}.")


if __name__ == "__main__":
    asyncio.run(main())
