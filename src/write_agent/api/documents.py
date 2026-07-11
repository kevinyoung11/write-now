from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from write_agent.core.auth import CurrentUserDep
from write_agent.models import Document, DocumentVersion
from write_agent.services.document_service import document_service

router = APIRouter(prefix="/documents", tags=["Documents"])


class CreateDocumentRequest(BaseModel):
    title: str = "Untitled"
    content_html: str = ""
    content_text: str = ""


class CreateVersionRequest(BaseModel):
    content_html: str
    content_text: str
    source: str = "manual_save"
    reason: str = "manual save"
    parent_version_id: int | None = None


class RollbackRequest(BaseModel):
    version_id: int


def _version_payload(version: DocumentVersion) -> dict:
    return {
        "id": version.id,
        "document_id": version.document_id,
        "parent_version_id": version.parent_version_id,
        "content_html": version.content_html,
        "content_text": version.content_text,
        "source": version.source,
        "reason": version.reason,
        "created_at": version.created_at.isoformat(),
    }


def _document_payload(document: Document, version: DocumentVersion) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "status": document.status,
        "current_version_id": document.current_version_id,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
        "current_version": _version_payload(version),
    }


@router.post("")
async def create_document(request: CreateDocumentRequest, user: CurrentUserDep):
    document, version = document_service.create_document(
        user_id=user.supabase_user_id,
        title=request.title,
        content_html=request.content_html,
        content_text=request.content_text,
    )
    return _document_payload(document, version)


@router.get("")
async def list_documents(user: CurrentUserDep):
    items = document_service.list_documents(user_id=user.supabase_user_id)
    return {
        "items": [
            {
                "id": document.id,
                "title": document.title,
                "status": document.status,
                "current_version_id": document.current_version_id,
                "updated_at": document.updated_at.isoformat(),
            }
            for document in items
        ]
    }


@router.get("/current")
async def get_current_document(user: CurrentUserDep):
    try:
        result = document_service.get_current_document(user_id=user.supabase_user_id)
        if result is None:
            return {"document": None}
        document, version = result
        return {"document": _document_payload(document, version)}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{document_id:int}")
async def get_document(document_id: int, user: CurrentUserDep):
    try:
        document, version = document_service.get_document(
            user_id=user.supabase_user_id,
            document_id=document_id,
        )
        return _document_payload(document, version)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/{document_id:int}")
async def delete_document(document_id: int, user: CurrentUserDep):
    try:
        document_service.delete_document(
            user_id=user.supabase_user_id,
            document_id=document_id,
        )
        return {"ok": True}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{document_id:int}/versions")
async def create_version(
    document_id: int,
    request: CreateVersionRequest,
    user: CurrentUserDep,
):
    try:
        version = document_service.create_version(
            user_id=user.supabase_user_id,
            document_id=document_id,
            content_html=request.content_html,
            content_text=request.content_text,
            source=request.source,
            reason=request.reason,
            parent_version_id=request.parent_version_id,
        )
        return _version_payload(version)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{document_id:int}/versions")
async def list_versions(document_id: int, user: CurrentUserDep):
    try:
        versions = document_service.list_versions(
            user_id=user.supabase_user_id,
            document_id=document_id,
        )
        return {"items": [_version_payload(version) for version in versions]}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{document_id:int}/rollback")
async def rollback(document_id: int, request: RollbackRequest, user: CurrentUserDep):
    try:
        document, version = document_service.rollback(
            user_id=user.supabase_user_id,
            document_id=document_id,
            version_id=request.version_id,
        )
        return _document_payload(document, version)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
