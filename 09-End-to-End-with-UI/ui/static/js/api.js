// api.js — thin fetch() wrapper that injects the session Bearer token
// and handles JSON serialization + error shapes.

import { getToken, logout } from './auth.js';

async function request(path, { method = 'GET', body, headers = {}, auth = true } = {}) {
  const opts = {
    method,
    headers: { 'Accept': 'application/json', ...headers },
  };

  if (auth) {
    const token = getToken();
    if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  }

  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  const resp = await fetch(path, opts);

  // Expired/invalid token → kick to login
  if (resp.status === 401 && auth) {
    logout({ redirect: true });
    throw new Error('sessão expirada — faça login novamente');
  }

  const text = await resp.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }

  if (!resp.ok) {
    const err = new Error(
      (data && data.error) ? `${data.error}${data.detail ? `: ${data.detail}` : ''}` : `HTTP ${resp.status}`
    );
    err.status = resp.status;
    err.data   = data;
    throw err;
  }

  return data;
}

export const api = {
  get:  (path, opts)       => request(path, { ...opts, method: 'GET' }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body }),
};
