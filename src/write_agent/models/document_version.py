from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class DocumentVersion(SQLModel, table=True):
    __tablename__ = "document_versions"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    user_id: str = Field(index=True)
    parent_version_id: Optional[int] = Field(default=None, index=True)
    content_html: str = Field(default="")
    content_text: str = Field(default="")
    source: str = Field(default="manual_save", index=True)
    reason: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now, index=True)

