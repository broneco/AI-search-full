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


class RelationshipInfo(BaseModel):
    relationship_type: str = Field("none", description="replaces, modifies or none")
    target_document_id: Optional[str] = Field(None, description="UUID of target document")
    target_document_title: Optional[str] = Field(None, description="Title of target document")


class DocumentConfirmedIngestRequest(BaseModel):
    title: str = Field(..., description="Document title")
    date: str = Field(..., description="Release date in YYYY-MM-DD")
    category: str = Field(..., description="Selected category key")
    relationship: RelationshipInfo = Field(default_factory=RelationshipInfo)
    temp_file_path: str = Field(..., description="Path to the temporary file on disk")
    original_filename: str = Field(..., description="Original filename")


class CategoryItem(BaseModel):
    key: str
    label: str
    description: str
    allowed_groups: List[str]
    role_name: Optional[str] = None


class CategoryConfigRequest(BaseModel):
    categories: List[CategoryItem]
    analysis_rules: str

