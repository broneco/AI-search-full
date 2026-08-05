import json
import logging
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.providers.blob_storage import BlobStorageProvider

logger = logging.getLogger(__name__)


class SemanticChunkingParams(BaseModel):
    threshold_type: str = Field("percentile", pattern="^(percentile|standard_deviation|absolute)$")
    threshold_value: float = Field(95.0, ge=0.0, le=100.0)
    sentence_splitter: str = Field("nltk", pattern="^(nltk|spacy|simple_regex)$")
    buffer_size: int = Field(1, ge=1, le=5)
    max_size: int = Field(3000, ge=500, le=10000)

class StructureChunkingParams(BaseModel):
    parser_type: str = Field("markdown", pattern="^(markdown|html|pdf_layout)$")
    preserve_tables: bool = Field(True)
    preserve_lists: bool = Field(True)
    heading_levels: List[str] = Field(default_factory=lambda: ["h1", "h2", "h3"])
    max_size: int = Field(4000, ge=500, le=10000)

class TokenChunkingParams(BaseModel):
    tokenizer_type: str = Field("cl100k_base", pattern="^(cl100k_base|o200k_base)$")
    size_tokens: int = Field(512, ge=64, le=4096)
    overlap_tokens: int = Field(64, ge=0, le=1024)

class AgenticChunkingParams(BaseModel):
    model_name: str = Field("gpt-4o-mini")
    custom_prompt: str = Field("")
    max_context_chars: int = Field(4000, ge=1000, le=16000)

class SearchConfigSchema(BaseModel):
    search_strategy: str = Field("hybrid", pattern="^(hybrid|vector|keyword)$")
    hybrid_strategy: str = Field("rrf", pattern="^(rrf|score_addition|union)$")
    vector_weight: float = Field(0.6, ge=0.0, le=1.0)
    keyword_weight: float = Field(0.4, ge=0.0, le=1.0)
    rrf_k: int = Field(60, ge=10, le=100)
    vector_limit: int = Field(50, ge=5, le=200)
    keyword_limit: int = Field(50, ge=5, le=200)
    final_limit: int = Field(8, ge=1, le=20)
    vector_final_limit: int = Field(5, ge=1, le=20)
    keyword_final_limit: int = Field(5, ge=1, le=20)
    score_threshold: float = Field(0.0, ge=0.0, le=1.0)
    freshness_boost: float = Field(0.0, ge=0.0, le=0.5)
    context_expansion: str = Field("none", pattern="^(none|siblings|page|section)$")
    context_expansion_size: int = Field(1, ge=1, le=3)
    chunk_size: int = Field(1500, ge=200, le=5000)
    chunk_overlap: int = Field(250, ge=0, le=1000)
    chunk_cross_page: bool = Field(False)
    overlap_cross_page: bool = Field(False)
    chunk_splitter_type: str = Field("recursive", pattern="^(recursive|character)$")
    context_max_tokens: int = Field(4000, ge=1000, le=30000)
    enrich_with_summary: bool = Field(False)
    summary_custom_prompt: str = Field("")

    # Advanced chunking strategy parameters
    chunking_strategy: str = Field("standard", pattern="^(standard|semantic|structure|token|agentic)$")
    semantic_params: SemanticChunkingParams = Field(default_factory=SemanticChunkingParams)
    structure_params: StructureChunkingParams = Field(default_factory=StructureChunkingParams)
    token_params: TokenChunkingParams = Field(default_factory=TokenChunkingParams)
    agentic_params: AgenticChunkingParams = Field(default_factory=AgenticChunkingParams)


class SearchConfigManager:
    def __init__(self) -> None:
        self.blob_provider = BlobStorageProvider()
        self.config_path = os.path.join(
            os.path.dirname(__file__), "search_config.json"
        )

    async def load_config(self) -> Dict[str, Any]:
        """Load search config from Azure Blob Storage or local disk."""
        config_data = None
        if self.blob_provider.is_configured():
            try:
                container = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
                blob_name = "config/search_config.json"
                logger.info(f"Loading search config from Azure Blob: {container}/{blob_name}")
                data = await self.blob_provider.download_blob(container, blob_name)
                config_data = json.loads(data.decode("utf-8"))
            except Exception as e:
                logger.warning(f"Failed to load search config from Azure Blob, falling back to local file: {e}")

        if config_data is None:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                except Exception as e:
                    logger.error(f"Error reading local search config file: {e}")
                    config_data = self.get_defaults()
            else:
                logger.warning(f"Search config file not found at {self.config_path}. Using defaults.")
                config_data = self.get_defaults()
        return config_data

    def load_config_sync(self) -> Dict[str, Any]:
        """Synchronous configuration load (for sync retrieval contexts, falling back to local)."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading local search config: {e}")
        return self.get_defaults()

    async def save_config(self, config_data: Dict[str, Any]) -> None:
        """Save search config to local disk and upload to Azure Blob Storage."""
        # Validate using Pydantic schema
        validated_config = SearchConfigSchema(**config_data).model_dump()

        # Save locally
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(validated_config, f, ensure_ascii=False, indent=2)

        # Upload to Azure Blob if configured
        if self.blob_provider.is_configured():
            try:
                container = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
                blob_name = "config/search_config.json"
                logger.info(f"Saving search config to Azure Blob: {container}/{blob_name}")
                config_bytes = json.dumps(validated_config, ensure_ascii=False, indent=2).encode("utf-8")
                await self.blob_provider.upload_blob(container, blob_name, config_bytes)
            except Exception as e:
                logger.error(f"Failed to upload search config to Azure Blob: {e}")

    def get_defaults(self) -> Dict[str, Any]:
        return {
            "search_strategy": "hybrid",
            "hybrid_strategy": "rrf",
            "vector_weight": 0.6,
            "keyword_weight": 0.4,
            "rrf_k": 60,
            "vector_limit": 50,
            "keyword_limit": 50,
            "final_limit": 5,
            "vector_final_limit": 5,
            "keyword_final_limit": 5,
            "score_threshold": 0.0,
            "freshness_boost": 0.0,
            "context_expansion": "none",
            "context_expansion_size": 1,
            "chunk_size": 1500,
            "chunk_overlap": 250,
            "chunk_cross_page": False,
            "overlap_cross_page": False,
            "chunk_splitter_type": "recursive",
            "context_max_tokens": 4000,
            "enrich_with_summary": False,
            "summary_custom_prompt": "",
            "chunking_strategy": "standard",
            "semantic_params": {
                "threshold_type": "percentile",
                "threshold_value": 95.0,
                "sentence_splitter": "nltk",
                "buffer_size": 1,
                "max_size": 3000
            },
            "structure_params": {
                "parser_type": "markdown",
                "preserve_tables": True,
                "preserve_lists": True,
                "heading_levels": ["h1", "h2", "h3"],
                "max_size": 4000
            },
            "token_params": {
                "tokenizer_type": "cl100k_base",
                "size_tokens": 512,
                "overlap_tokens": 64
            },
            "agentic_params": {
                "model_name": "gpt-4o-mini",
                "custom_prompt": "",
                "max_context_chars": 4000
            }
        }
