from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

class RightsStatus(StrEnum):
    UNKNOWN = "unknown"
    OPEN = "open"
    RESTRICTED = "restricted"
    LICENSED = "licensed"
    PUBLIC_DOMAIN = "public_domain"
    DISALLOWED = "disallowed"

class DocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    HTML = "html"
    TEXT = "text"
    UNKNOWN = "unknown"

class DocumentIngest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=1000)
    text: str | None = None
    content_base64: str | None = None
    source_name: str = "manual"
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    language: str | None = None
    metadata: dict = Field(default_factory=dict)

class DocumentOut(BaseModel):
    id: str
    title: str | None
    canonical_hash: str
    text_hash: str
    format: str
    created_at: datetime

class SimilarityRequest(BaseModel):
    text: str = Field(min_length=50)
    limit: int = Field(default=10, ge=1, le=100)

class DiscoveryRecord(BaseModel):
    url: HttpUrl
    title: str | None = None
    source: str
    metadata: dict = Field(default_factory=dict)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
