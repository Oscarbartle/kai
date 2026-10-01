// Same-origin by design: this app is served by kai-server from the same
// address as the API, so every call is a relative path (and `npm run dev`
// proxies the same paths) — no base URL to configure, no CORS.

const TOKEN_KEY = 'kai.token';

/** The server said no to our token (as opposed to being unreachable). */
export class AuthError extends Error {}

// localStorage can throw or come back empty (private windows, blocked site
// data) — the app has to keep working, it just can't remember the token.
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* works for this session, just won't be remembered */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing to clear */
  }
}

async function request(path: string, token: string | null, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    return await fetch(path, { ...init, headers });
  } catch {
    throw new Error("Couldn't reach the server — check your connection.");
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 401) throw new AuthError('That token was rejected.');
  if (!res.ok) {
    let message = `The server returned ${res.status}.`;
    try {
      const body = await res.json();
      if (body?.error) message = body.error;
    } catch {
      /* not JSON — keep the status message */
    }
    throw new Error(message);
  }
  // Some writes (DELETE) answer with an empty body.
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return parse<T>(await request(path, getToken()));
}

/** POST / PATCH / DELETE with an optional JSON body. */
export async function apiSend<T = void>(
  method: 'POST' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown
): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  return parse<T>(await request(path, getToken(), init));
}

/** Checks a token against the server *before* it's saved. */
export async function verifyToken(token: string): Promise<void> {
  const res = await request('/status', token);
  if (res.status === 401) throw new AuthError('That token was rejected.');
  if (!res.ok) throw new Error(`The server returned ${res.status}.`);
}
