from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from write_agent.core.database import engine
from write_agent.core.schema import ensure_database_schema
from write_agent.models import Document, DocumentVersion


class DocumentService:
    def ensure_schema(self) -> None:
        ensure_database_schema(engine)

    def create_document(
        self,
        *,
        user_id: str,
        title: str,
        content_html: str,
        content_text: str,
    ) -> tuple[Document, DocumentVersion]:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            document = Document(user_id=user_id, title=title or "Untitled")
            session.add(document)
            session.flush()

            version = DocumentVersion(
                document_id=int(document.id),
                user_id=user_id,
                parent_version_id=None,
                content_html=content_html,
                content_text=content_text,
                source="initial",
                reason="initial document",
            )
            session.add(version)
            session.flush()

            document.current_version_id = version.id
            document.updated_at = datetime.now()
            session.add(document)
            session.commit()
            session.refresh(document)
            session.refresh(version)
            return document, version

    def list_documents(self, *, user_id: str) -> list[Document]:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            return list(
                session.exec(
                    select(Document)
                    .where(Document.user_id == user_id, Document.status == "active")
                    .order_by(Document.updated_at.desc())
                )
            )

    def get_current_document(
        self, *, user_id: str
    ) -> tuple[Document, DocumentVersion] | None:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            document = session.exec(
                select(Document)
                .where(Document.user_id == user_id, Document.status == "active")
                .order_by(Document.updated_at.desc())
            ).first()
            if document is None:
                return None
            version = session.get(DocumentVersion, document.current_version_id)
            if version is None or version.user_id != user_id:
                raise ValueError("Current version not found")
            return document, version

    def delete_document(self, *, user_id: str, document_id: int) -> None:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            document = session.get(Document, document_id)
            if (
                document is None
                or document.user_id != user_id
                or document.status != "active"
            ):
                raise ValueError("Document not found")
            document.status = "deleted"
            document.updated_at = datetime.now()
            session.add(document)
            session.commit()

    def get_document(
        self, *, user_id: str, document_id: int
    ) -> tuple[Document, DocumentVersion]:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            document = session.get(Document, document_id)
            if document is None or document.user_id != user_id:
                raise ValueError("Document not found")
            version = session.get(DocumentVersion, document.current_version_id)
            if version is None or version.user_id != user_id:
                raise ValueError("Current version not found")
            return document, version

    def create_version(
        self,
        *,
        user_id: str,
        document_id: int,
        content_html: str,
        content_text: str,
        source: str,
        reason: str,
        parent_version_id: Optional[int] = None,
    ) -> DocumentVersion:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            document = session.get(Document, document_id)
            if document is None or document.user_id != user_id:
                raise ValueError("Document not found")
            parent_id = (
                parent_version_id
                if parent_version_id is not None
                else document.current_version_id
            )
            if parent_id is not None:
                parent = session.get(DocumentVersion, parent_id)
                if (
                    parent is None
                    or parent.user_id != user_id
                    or parent.document_id != document_id
                ):
                    raise ValueError("Parent version not found")
            version = DocumentVersion(
                document_id=document_id,
                user_id=user_id,
                parent_version_id=parent_id,
                content_html=content_html,
                content_text=content_text,
                source=source,
                reason=reason,
            )
            session.add(version)
            session.flush()
            document.current_version_id = version.id
            document.updated_at = datetime.now()
            session.add(document)
            session.commit()
            session.refresh(version)
            return version

    def list_versions(self, *, user_id: str, document_id: int) -> list[DocumentVersion]:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            document = session.get(Document, document_id)
            if document is None or document.user_id != user_id:
                raise ValueError("Document not found")
            return list(
                session.exec(
                    select(DocumentVersion)
                    .where(
                        DocumentVersion.document_id == document_id,
                        DocumentVersion.user_id == user_id,
                    )
                    .order_by(DocumentVersion.created_at.desc())
                )
            )

    def rollback(
        self, *, user_id: str, document_id: int, version_id: int
    ) -> tuple[Document, DocumentVersion]:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            document = session.get(Document, document_id)
            version = session.get(DocumentVersion, version_id)
            if document is None or document.user_id != user_id:
                raise ValueError("Document not found")
            if (
                version is None
                or version.user_id != user_id
                or version.document_id != document_id
            ):
                raise ValueError("Version not found")
            document.current_version_id = version.id
            document.updated_at = datetime.now()
            session.add(document)
            session.commit()
            session.refresh(document)
            return document, version


document_service = DocumentService()
