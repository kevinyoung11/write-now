export function authHeaders(includeJson = true): HeadersInit {
  const headers: Record<string, string> = {};
  if (includeJson) {
    headers['Content-Type'] = 'application/json';
  }

  const accessToken = localStorage.getItem('supabase-access-token');
  const devUserId = localStorage.getItem('user-id');

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  } else if (devUserId) {
    headers['X-Dev-User-Id'] = devUserId;
  }

  return headers;
}

export async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

