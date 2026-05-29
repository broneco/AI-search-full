from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    title: str = Field(..., description="The title of the document.")
    source_type: str = Field(..., description="Document source type (e.g. 'local', 'sharepoint', 'blob').")
    source_uri: str = Field(..., description="Source URI/path of the document.")
    document_type: str = Field(..., description="Type of document (e.g. 'policy', 'handbook').")
    content: str = Field(..., description="String text chunk content to embed and save.")
    language: str = Field("en", description="Document language.")
    security_acl: Optional[Dict[str, List[str]]] = Field(
        default=None, description="ACL allowed groups structure (e.g. {'allowed_groups': ['HR']})."
    )
    metadata_json: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata dictionary to store with document and chunk."
    )


class DocumentIngestResponse(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    status: str
