import os
import re
import json
import logging
import datetime
import argparse
import asyncio
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.providers.azure_openai import AzureOpenAIProvider
from app.providers.llm import ChatMessage
from app.ingestion.extraction import DocumentExtractor
from app.storage.models import DBDocument
from app.storage.db import SessionLocal
from app.providers.blob_storage import BlobStorageProvider

logger = logging.getLogger(__name__)


class MetadataTagger:
    """Extracts suggested metadata from a document (category, release date, replacement relationships)."""

    def __init__(self, db_session: Optional[Session] = None) -> None:
        self.db = db_session
        self.extractor = DocumentExtractor()
        self.llm = AzureOpenAIProvider()
        self.blob_provider = BlobStorageProvider()
        self.config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "core", "classification_config.json"
        )

    async def load_config(self) -> Dict[str, Any]:
        """Load the classification configuration from Blob Storage or local disk."""
        config_data = None
        if self.blob_provider.is_configured():
            try:
                container = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
                blob_name = "config/classification_config.json"
                logger.info(f"Loading config from Azure Blob: {container}/{blob_name}")
                data = await self.blob_provider.download_blob(container, blob_name)
                config_data = json.loads(data.decode("utf-8"))
            except Exception as e:
                logger.warning(f"Failed to load config from Azure Blob, falling back to local file: {e}")
        
        if config_data is None:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            else:
                logger.warning(f"Config file not found at {self.config_path}. Using fallback defaults.")
                config_data = {
                    "categories": [
                        {
                            "key": "3f6b7c5e-8e9d-4c3a-8b2f-7a1b3c5e7d9f",
                            "label": "Vedení (Management)",
                            "description": "Vedení společnosti, strategická rozhodnutí, zápisy z porad vedení.",
                            "role_name": "Management",
                            "allowed_groups": ["Management"]
                        },
                        {
                            "key": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                            "label": "Personální (HR)",
                            "description": "Lidské zdroje, nábor zaměstnanců, pracovní smlouvy, mzdová politika.",
                            "role_name": "HR",
                            "allowed_groups": ["Management", "HR"]
                        },
                        {
                            "key": "f7e6d5c4-b3a2-1e0f-9d8c-7b6a5e4d3c2b",
                            "label": "Finanční (Finance)",
                            "description": "Finance, účetní směrnice, rozpočty, fakturační procesy.",
                            "role_name": "Finance",
                            "allowed_groups": ["Management", "Finance"]
                        },
                        {
                            "key": "c9b8a7d6-e5f4-3c2b-1a0d-9e8f7a6b5c4d",
                            "label": "Zaměstnanecké (User)",
                            "description": "Obecné vnitřní předpisy, bezpečnost práce, docházkové systémy.",
                            "role_name": "User",
                            "allowed_groups": ["Management", "HR", "Finance", "User"]
                        }
                    ],
                    "analysis_rules": "Zaměř se na vyhledávání důležitých názvů, čísel a dat."
                }
        return config_data

    async def save_config(self, config_data: Dict[str, Any]) -> None:
        """Save the classification configuration to Blob Storage and local disk."""
        # First save locally
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
            
        # Then upload to Azure Blob if configured
        if self.blob_provider.is_configured():
            try:
                container = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
                blob_name = "config/classification_config.json"
                logger.info(f"Saving config to Azure Blob: {container}/{blob_name}")
                config_bytes = json.dumps(config_data, ensure_ascii=False, indent=2).encode("utf-8")
                await self.blob_provider.upload_blob(container, blob_name, config_bytes)
            except Exception as e:
                logger.error(f"Failed to upload config to Azure Blob: {e}")

    def scan_date_candidates(self, text: str) -> List[str]:
        """Scan the text using regular expressions to find date candidate snippets."""
        # Regexes for:
        # 1. DD.MM.YYYY or D.M.YYYY (e.g., 24.12.2026, 5. 5. 2026)
        # 2. YYYY-MM-DD
        # 3. Czech written months (e.g. 15. ledna 2026)
        patterns = [
            r"\b\d{1,2}\.\s*\d{1,2}\.\s*\d{4}\b",
            r"\b\d{4}-\d{2}-\d{2}\b",
            r"\b\d{1,2}\.\s*(?:ledna|ledan|února|unora|března|brezna|dubna|května|kvetna|června|cervna|července|cervence|srpna|září|zari|října|rijna|listopadu|prosince)\s*\d{4}\b"
        ]
        
        candidates = []
        lines = text.splitlines()
        
        for idx, line in enumerate(lines):
            has_match = False
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    has_match = True
                    break
            
            if has_match:
                # Get context around the matching line (+/- 2 lines)
                start = max(0, idx - 2)
                end = min(len(lines), idx + 3)
                context_snippet = "\n".join(lines[start:end])
                candidates.append(context_snippet)
                
                # Limit to first 5 candidate snippets to avoid bloating LLM context
                if len(candidates) >= 5:
                    break
                    
        return candidates

    async def determine_release_date(self, text: str, file_path: str) -> str:
        """Analyze date candidates using the LLM and return YYYY-MM-DD, falling back to metadata."""
        candidates = self.scan_date_candidates(text)
        
        if candidates:
            candidates_text = "\n---\n".join(candidates)
            system_prompt = (
                "Jsi asistent pro analýzu dokumentů. Tvým úkolem je z poskytnutých fragmentů textu "
                "identifikovat OFICIÁLNÍ DATUM VYDÁNÍ nebo ÚČINNOSTI tohoto dokumentu.\n"
                "Pravidla:\n"
                "- Odpověz výhradně ve formátu YYYY-MM-DD (např. 2026-06-11).\n"
                "- Pokud z fragmentů nelze jednoznačně datum vydání určit, odpověz přesně slovem: null\n"
                "- Neuváděj žádný jiný text, vysvětlení ani uvozovky."
            )
            
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=f"Zde jsou nalezené fragmenty obsahující data:\n{candidates_text}")
            ]
            
            try:
                result = await self.llm.generate(messages, model_profile="flash", temperature=0.0)
                date_str = result.strip().replace('"', '').replace("'", "")
                # Simple validation of YYYY-MM-DD
                if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                    logger.info(f"LLM successfully extracted release date: {date_str}")
                    return date_str
            except Exception as e:
                logger.error(f"Failed to determine date using LLM: {e}")
 
        # Fallback 1: Read PDF metadata creation date if available
        try:
            from pypdf import PdfReader
            _, ext = os.path.splitext(file_path)
            if ext.lower() == ".pdf":
                reader = PdfReader(file_path)
                meta = reader.metadata
                if meta and meta.creation_date:
                    dt = meta.creation_date
                    logger.info(f"Using PDF metadata creation date: {dt.strftime('%Y-%m-%d')}")
                    return dt.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Could not read PDF metadata date: {e}")

        # Fallback 2: File system creation time or current date
        try:
            mtime = os.path.getmtime(file_path)
            dt = datetime.datetime.fromtimestamp(mtime)
            logger.info(f"Using file modification date fallback: {dt.strftime('%Y-%m-%d')}")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            today = datetime.date.today().strftime("%Y-%m-%d")
            logger.info(f"Using current date fallback: {today}")
            return today

    async def classify_category(self, text_excerpt: str, config: Dict[str, Any]) -> str:
        """Classify the document into one of the configured categories using LLM and map it to a UUID key."""
        categories_info = []
        for cat in config["categories"]:
            categories_info.append({
                "role_name": cat.get("role_name"),
                "label": cat.get("label"),
                "description": cat.get("description")
            })
        categories_str = json.dumps(categories_info, ensure_ascii=False, indent=2)
        rules = config.get("analysis_rules", "")
        
        system_prompt = (
            "Jsi expert na klasifikaci korporátních směrnic a dokumentů společnosti Dolphin Consulting.\n"
            "Zde jsou dostupné kategorie v JSON formátu:\n"
            f"{categories_str}\n\n"
            f"Dodatečná pravidla pro analýzu:\n{rules}\n\n"
            "Tvým úkolem je přečíst úryvek dokumentu a rozhodnout, do které JEDNÉ kategorie spadá.\n"
            "Odpověz pouze názvem role vybrané kategorie (role_name), např. 'HR', 'Management', 'Finance' nebo 'User'.\n"
            "Neuváděj žádný jiný text, uvozovky ani vysvětlení. Odpověz pouze názvem role (role_name)."
        )
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=f"Zde je začátek dokumentu k analýze:\n{text_excerpt}")
        ]
        
        fallback_key = "c9b8a7d6-e5f4-3c2b-1a0d-9e8f7a6b5c4d"  # User category UUID
        
        # Find user category key in config if exists
        for cat in config["categories"]:
            role_val = cat.get("role_name") or cat.get("key") or ""
            if role_val.lower() == "user":
                fallback_key = cat.get("key")
                break
                
        try:
            result = await self.llm.generate(messages, model_profile="flash", temperature=0.0)
            role_name = result.strip().replace('"', '').replace("'", "")
            
            # Map role_name back to UUID key
            for cat in config["categories"]:
                role_val = cat.get("role_name") or cat.get("key") or ""
                if role_val.lower() == role_name.lower():
                    logger.info(f"LLM classified role: {role_name} -> key: {cat['key']}")
                    return cat["key"]
                    
            logger.warning(f"LLM returned unmatched role name '{role_name}'. Defaulting to fallback category key.")
        except Exception as e:
            logger.error(f"Failed to classify category using LLM: {e}")
            
        return fallback_key

    async def detect_relationships(self, text_excerpt: str) -> Dict[str, Any]:
        """Detect whether this document replaces or modifies an existing document in the DB."""
        relationship_fallback = {"relationship_type": "none", "target_document_id": None, "target_document_title": None}
        
        if not self.db:
            logger.info("No DB session provided, skipping relationship detection.")
            return relationship_fallback
            
        try:
            # Query active documents in database
            stmt = select(DBDocument).where(DBDocument.freshness_status == "current")
            docs = self.db.execute(stmt).scalars().all()
            if not docs:
                return relationship_fallback
                
            existing_docs = [{"document_id": str(d.document_id), "title": d.title} for d in docs]
            existing_docs_str = json.dumps(existing_docs, ensure_ascii=False, indent=2)
            
            system_prompt = (
                "Jsi analytik dokumentů. Analyzuješ úvod nového dokumentu a porovnáváš ho se seznamem stávajících dokumentů v databázi.\n"
                "Seznam existujících dokumentů (formát JSON):\n"
                f"{existing_docs_str}\n\n"
                "Úkol:\n"
                "Zjisti, zda nový dokument obsahuje formulace indikující, že nahrazuje (replaces) nebo upravuje/doplňuje (modifies) některý z existujících dokumentů.\n"
                "Typické české fráze:\n"
                "- 'nahrazuje dokument...', 'ruší směrnici XY', 'tato směrnice nahrazuje...', 'tímto se ruší platnost...'\n"
                "- 'upravuje směrnici XY', 'doplňuje dokument...', 'mění se ustanovení...'\n\n"
                "Musíš odpovědět výhradně ve formátu JSON s následující strukturou:\n"
                "{\n"
                "  \"relationship_type\": \"replaces\" | \"modifies\" | \"none\",\n"
                "  \"target_document_id\": \"UUID existujícího dokumentu\" nebo null,\n"
                "  \"target_document_title\": \"Název existujícího dokumentu\" nebo null\n"
                "}\n"
                "Pravidla:\n"
                "- Vyber pouze existující dokument ze seznamu výše, pokud se v textu jednoznačně mluví o něm.\n"
                "- Odpověz pouze čistým JSON. Žádný doprovodný text, vysvětlení ani markdown bloky ```json."
            )
            
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=f"Zde je úvod nového dokumentu:\n{text_excerpt}")
            ]
            
            result = await self.llm.generate(messages, model_profile="flash", temperature=0.0)
            cleaned_result = result.strip()
            
            # Strip markdown if LLM returned it anyway
            if cleaned_result.startswith("```"):
                cleaned_result = re.sub(r"^```(?:json)?\n", "", cleaned_result)
                cleaned_result = re.sub(r"\n```$", "", cleaned_result)
                cleaned_result = cleaned_result.strip()
                
            data = json.loads(cleaned_result)
            
            # Basic validation
            rel_type = data.get("relationship_type", "none")
            if rel_type not in ("replaces", "modifies", "none"):
                data["relationship_type"] = "none"
                data["target_document_id"] = None
                data["target_document_title"] = None
                
            logger.info(f"LLM detected relationship: {data}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to detect relationships using LLM: {e}")
            return relationship_fallback

    async def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Perform text extraction and run LLM analyses to extract draft metadata suggestions."""
        logger.info(f"Starting metadata draft analysis for: {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # 1. Extract pages (we only need the first 2 pages for date, category and relationship analysis)
        pages = self.extractor.extract(file_path)
        if not pages:
            raise ValueError(f"Could not extract any text from: {file_path}")
            
        first_pages_text = "\n".join([p.text for p in pages[:2]])
        full_text = "\n".join([p.text for p in pages])
        
        # Load configuration
        config = await self.load_config()
        
        # Run date extraction, category classification and relationships concurrently
        date_task = self.determine_release_date(full_text, file_path)
        category_task = self.classify_category(first_pages_text, config)
        relationship_task = self.detect_relationships(first_pages_text)
        
        date_str, category_key, relationship = await asyncio.gather(
            date_task, category_task, relationship_task
        )
        
        suggested_title = os.path.splitext(os.path.basename(file_path))[0]
        
        return {
            "title": suggested_title,
            "suggested_date": date_str,
            "suggested_category": category_key,
            "relationship": relationship,
            "original_filename": os.path.basename(file_path)
        }


# Standing alone CLI executor script
async def run_cli(file_path: str):
    init_db_needed = False
    db = None
    try:
        db = SessionLocal()
        # Ping DB
        from sqlalchemy import text
        db.execute(text("SELECT 1;"))
    except Exception:
        logger.warning("PostgreSQL connection offline. Relationship checks will be disabled.")
        db = None

    tagger = MetadataTagger(db_session=db)
    try:
        result = await tagger.analyze_file(file_path)
        print("\n=== NAVRŽENÁ METADATA PRO DOKUMENT ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("=======================================\n")
    except Exception as e:
        print(f"Chyba při analýze dokumentu: {e}")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    parser = argparse.ArgumentParser(description="Automatické tagování dokumentů pomocí LLM")
    parser.add_argument("--file", required=True, help="Cesta k souboru (PDF nebo TXT)")
    args = parser.parse_args()
    
    asyncio.run(run_cli(args.file))
