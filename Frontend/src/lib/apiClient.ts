import { useAppStore } from '@/store/appStore';

const API_URL = import.meta.env.VITE_API_URL ?? '/api';
let accessToken: string | null = null;
let csrfToken: string | null = null;
let csrfPromise: Promise<string> | null = null;
let refreshPromise: Promise<boolean> | null = null;

export class ApiError extends Error {
  constructor(public readonly status: number, message = 'No fue posible completar la solicitud.') {
    super(message);
    this.name = 'ApiError';
  }
}

async function responseError(response: Response): Promise<ApiError> {
  let message = 'No fue posible completar la solicitud.';
  try {
    const data = await response.json() as { detail?: unknown };
    if (typeof data.detail === 'string') message = data.detail;
    else if (data.detail !== undefined) message = JSON.stringify(data.detail);
    else {
      const firstMessage = Object.values(data).flatMap(value => Array.isArray(value) ? value : [value])
        .find(value => typeof value === 'string');
      if (typeof firstMessage === 'string') message = firstMessage;
    }
  } catch {
    message = response.statusText || message;
  }
  return new ApiError(response.status, message);
}

export const tokenMemory = {
  get: () => accessToken,
  set: (value: string | null) => { accessToken = value; },
};

async function getCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!csrfPromise) {
    csrfPromise = fetch(`${API_URL}/auth/csrf/`, { credentials: 'include' })
      .then(async response => {
        if (!response.ok) throw await responseError(response);
        const data = await response.json() as { token: string };
        csrfToken = data.token;
        return data.token;
      })
      .finally(() => { csrfPromise = null; });
  }
  return csrfPromise;
}

async function refresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const csrf = await getCsrfToken();
        const response = await fetch(`${API_URL}/auth/refresh/`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'X-CSRFToken': csrf },
        });
        if (!response.ok) return false;
        accessToken = (await response.json() as { access: string }).access;
        return true;
      } catch {
        return false;
      }
    })().finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

function expireSession() {
  accessToken = null;
  useAppStore.getState().setUser(null);
  if (typeof BroadcastChannel !== 'undefined') {
    const channel = new BroadcastChannel('jg-session');
    channel.postMessage('logout');
    channel.close();
  }
  if (window.location.pathname !== '/login') window.location.assign('/login');
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase();
  const authWrite = path.startsWith('/auth/') && !['GET', 'HEAD', 'OPTIONS'].includes(method);
  const csrf = authWrite ? await getCsrfToken() : null;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (csrf) headers.set('X-CSRFToken', csrf);

  const send = () => fetch(`${API_URL}${path}`, { ...init, method, credentials: 'include', headers });
  let response = await send();
  if (response.status === 401 && accessToken) {
    if (await refresh()) {
      headers.set('Authorization', `Bearer ${accessToken}`);
      response = await send();
    }
    if (response.status === 401) expireSession();
  }
  if (!response.ok) throw await responseError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function apiDownload(path: string, fallbackName: string): Promise<void> {
  const headers = new Headers();
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  let response = await fetch(`${API_URL}${path}`, { credentials: 'include', headers });
  if (response.status === 401 && accessToken) {
    if (await refresh()) {
      headers.set('Authorization', `Bearer ${accessToken}`);
      response = await fetch(`${API_URL}${path}`, { credentials: 'include', headers });
    }
    if (response.status === 401) expireSession();
  }
  if (!response.ok) throw await responseError(response);
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
