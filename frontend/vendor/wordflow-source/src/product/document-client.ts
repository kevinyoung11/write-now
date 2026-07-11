import { config } from '../config/config';
import { authHeaders, parseJsonResponse } from './api-client';

export interface DocumentVersionPayload {
  id: number;
  document_id: number;
  parent_version_id?: number | null;
  content_html: string;
  content_text: string;
  source: string;
  reason: string;
  created_at?: string;
}

export interface DocumentPayload {
  id: number;
  title: string;
  status?: string;
  current_version_id: number;
  updated_at?: string;
  current_version: DocumentVersionPayload;
}

export interface DocumentListItemPayload {
  id: number;
  title: string;
  status?: string;
  current_version_id: number;
  updated_at?: string;
}

export interface CurrentDocumentPayload {
  document: DocumentPayload | null;
}

export async function listDocuments(): Promise<DocumentListItemPayload[]> {
  const response = await fetch(config.urls.documentsEndpoint, {
    headers: authHeaders(false)
  });
  const payload = await parseJsonResponse<{ items: DocumentListItemPayload[] }>(
    response
  );
  return payload.items;
}

export async function getDocument(documentId: number): Promise<DocumentPayload> {
  const response = await fetch(`${config.urls.documentsEndpoint}/${documentId}`, {
    headers: authHeaders(false)
  });
  return parseJsonResponse<DocumentPayload>(response);
}

export async function getCurrentDocument(): Promise<DocumentPayload | null> {
  const response = await fetch(`${config.urls.documentsEndpoint}/current`, {
    headers: authHeaders(false)
  });
  const payload = await parseJsonResponse<CurrentDocumentPayload>(response);
  return payload.document;
}

export async function createDocument(
  title: string,
  contentHtml: string,
  contentText: string
): Promise<DocumentPayload> {
  const response = await fetch(config.urls.documentsEndpoint, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      title,
      content_html: contentHtml,
      content_text: contentText
    })
  });
  return parseJsonResponse<DocumentPayload>(response);
}

export async function deleteDocument(documentId: number): Promise<void> {
  const response = await fetch(`${config.urls.documentsEndpoint}/${documentId}`, {
    method: 'DELETE',
    headers: authHeaders(false)
  });
  await parseJsonResponse<{ ok: boolean }>(response);
}

export async function createDocumentVersion(
  documentId: number,
  payload: {
    content_html: string;
    content_text: string;
    source: string;
    reason: string;
    parent_version_id?: number;
  }
): Promise<DocumentVersionPayload> {
  const response = await fetch(`${config.urls.documentsEndpoint}/${documentId}/versions`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(payload)
  });
  return parseJsonResponse<DocumentVersionPayload>(response);
}
