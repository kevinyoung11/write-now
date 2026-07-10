import { config } from '../config/config';

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
  current_version: DocumentVersionPayload;
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export async function createDocument(
  title: string,
  contentHtml: string,
  contentText: string
): Promise<DocumentPayload> {
  const response = await fetch(config.urls.documentsEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      content_html: contentHtml,
      content_text: contentText
    })
  });
  return parseJsonResponse<DocumentPayload>(response);
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return parseJsonResponse<DocumentVersionPayload>(response);
}

