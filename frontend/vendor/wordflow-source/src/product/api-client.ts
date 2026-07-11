export function authHeaders(includeJson = true): HeadersInit {
  const headers: Record<string, string> = {};
  if (includeJson) {
    headers['Content-Type'] = 'application/json';
  }

  const accessToken = localStorage.getItem('supabase-access-token');

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  return headers;
}

export function hasAuthToken() {
  return Boolean(localStorage.getItem('supabase-access-token'));
}

export function saveAuthSession(payload: { access_token: string; email?: string }) {
  localStorage.setItem('supabase-access-token', payload.access_token);
  if (payload.email) {
    localStorage.setItem('supabase-user-email', payload.email);
  }
}

export function clearAuthToken() {
  localStorage.removeItem('supabase-access-token');
  localStorage.removeItem('supabase-user-email');
}

export async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}
