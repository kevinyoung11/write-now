import { config } from '../config/config';
import { saveAuthSession } from './api-client';

export interface SupabaseAuthSession {
  access_token: string;
  token_type?: string;
  expires_in?: number;
  refresh_token?: string;
  user?: {
    id?: string;
    email?: string;
  };
}

export async function signInWithPassword(
  email: string,
  password: string
): Promise<SupabaseAuthSession> {
  const response = await fetch(
    `${config.supabaseAuth.url}/auth/v1/token?grant_type=password`,
    {
      method: 'POST',
      headers: {
        apikey: config.supabaseAuth.anonKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email, password })
    }
  );

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const session = (await response.json()) as SupabaseAuthSession;
  if (!session.access_token) {
    throw new Error('Supabase did not return an access token');
  }

  saveAuthSession({
    access_token: session.access_token,
    email: session.user?.email ?? email
  });

  return session;
}
