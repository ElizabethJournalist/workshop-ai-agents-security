// auth.js — Cognito login + session helpers.

const KEY = 'govdemo.session';

export function getSession() {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function getToken() { return getSession()?.token || ''; }

export function getUser() {
  const s = getSession();
  return s ? { email: s.email, groups: s.groups || [] } : null;
}

export async function login(email, password) {
  const resp = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const code = data.error || `http_${resp.status}`;
    throw new Error(code);
  }
  sessionStorage.setItem(KEY, JSON.stringify(data));
  return data;
}

export function logout({ redirect = true } = {}) {
  sessionStorage.removeItem(KEY);
  if (redirect) window.location.href = '/';
}

export function requireAuth() {
  const s = getSession();
  if (!s || !s.token) {
    window.location.href = '/';
    throw new Error('unauthenticated');
  }
  return s;
}
