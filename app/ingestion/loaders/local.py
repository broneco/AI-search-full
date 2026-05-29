import os
import logging
from typing import List

logger = logging.getLogger(__name__)


def list_local_files(directory_path: str, extensions: List[str] = [".pdf", ".txt"]) -> List[str]:
    """Scan a local directory and return absolute paths to all matching files.

    Creates the directory if it does not exist.
    """
    if not os.path.exists(directory_path):
        logger.info(f"Directory {directory_path} does not exist. Creating it.")
        os.makedirs(directory_path, exist_ok=True)
        return []

    discovered_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() in extensions:
                discovered_files.append(os.path.abspath(os.path.join(root, file)))

    logger.info(f"Scanned {directory_path} and found {len(discovered_files)} matching files.")
    return discovered_files
