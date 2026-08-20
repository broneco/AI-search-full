import sys
import time
import argparse
import logging
from app.storage.db import SessionLocal, init_db
from app.storage.models import DBUser, DBChatThread, DBChatMessage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reset_users")


def main():
    parser = argparse.ArgumentParser(description="Dedicated administrative script to reset user accounts and chat history.")
    parser.add_argument("--force", action="store_true", help="Force deletion without interactive confirmation prompt")
    args = parser.parse_args()

    if not args.force:
        print("⚠️ CAUTION: This will delete ALL user accounts, passwords, and chat history.")
        confirm = input("Type 'RESET USERS' to confirm: ")
        if confirm != "RESET USERS":
            print("Aborted. No users were modified.")
            sys.exit(0)

    logger.info("Resetting user accounts and chat history...")
    for attempt in range(1, 4):
        try:
            with SessionLocal() as db_session:
                msgs = db_session.query(DBChatMessage).delete()
                threads = db_session.query(DBChatThread).delete()
                users = db_session.query(DBUser).delete()
                db_session.commit()
                logger.info(f"Deleted {msgs} messages, {threads} threads, and {users} user accounts.")
            break
        except Exception as e:
            logger.warning(f"Reset users attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(5)
            else:
                raise e

    logger.info("Re-initializing default demo user...")
    init_db()
    logger.info("User accounts reset complete.")


if __name__ == "__main__":
    main()
