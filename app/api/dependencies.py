from typing import Generator
from sqlalchemy.orm import Session
from app.storage.db import SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    """Provide a database session local transactions generator."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
