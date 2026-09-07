// configuracoes.js — informações da sessão + preferências.
import { api } from '../api.js';
import { getUser, getSession, requireAuth } from '../auth.js';
import { mountLayout } from '../layout.js';

requireAuth();
mountLayout({ active: 'configuracoes', title: 'Configurações' });

const $session = document.getElementById('session-body');
const $portal  = document.getElementById('portal-body');
const $claims  = document.getElementById('claims-body');

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function kv(k, v) {
  return `<div class="kv"><span class="kv-k">${escapeHtml(k)}</span><span class="kv-v mono">${escapeHtml(v ?? '—')}</span></div>`;
}
function decodeJwt(token) {
  try {
    const payload = token.split('.')[1];
    const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4);
    return JSON.parse(atob(padded.replace(/-/g, '+').replace(/_/g, '/')));
  } catch { return {}; }
}

function renderSession() {
  const u = getUser() || {};
  const s = getSession() || {};
  const expIso = s.exp ? new Date(s.exp * 1000).toISOString() : null;
  $session.innerHTML = `
    ${kv('E-mail', u.email)}
    ${kv('Grupos', (u.groups || []).join(', '))}
    ${kv('Token (primeiros 24 chars)', (s.token || '').slice(0, 24) + '…')}
    ${kv('Expira em', expIso)}
  `;
}

async function renderPortal() {
  try {
    const c = await api.get('/api/config/public');
    const specs = (c.specialists || []).map(s => `
      <div class="kv">
        <span class="kv-k">${escapeHtml(s.name)}</span>
        <span class="kv-v mono ${s.configured ? 'text-permit' : 'text-deny'}">${s.configured ? 'configurado' : 'AUSENTE'}</span>
      </div>
    `).join('');
    $portal.innerHTML = `
      ${kv('Setor',        c.sector)}
      ${kv('Modelo',       c.model)}
      ${kv('Gateway URL',  c.gatewayUrl)}
      ${kv('Cognito App',  c.cognitoClientId)}
      <div class="subheader">Runtimes especialistas</div>
      ${specs}
    `;
  } catch (e) {
    $portal.innerHTML = `<div class="error-line">Falha: ${escapeHtml(e.message)}</div>`;
  }
}

function renderClaims() {
  const s = getSession() || {};
  const claims = decodeJwt(s.token || '');
  if (!claims || !Object.keys(claims).length) {
    $claims.innerHTML = '<div class="governance-empty">sem token</div>';
    return;
  }
  const entries = Object.entries(claims).map(([k, v]) => {
    const display = typeof v === 'object' ? JSON.stringify(v) : String(v);
    return kv(k, display);
  }).join('');
  $claims.innerHTML = entries;
}

// Preferences
const PREF_CONTRAST = 'agentcore.pref.contrast';
const PREF_DEBUG    = 'agentcore.pref.debug';

const $contrast = document.getElementById('pref-contrast');
const $debug    = document.getElementById('pref-debug');

$contrast.checked = localStorage.getItem(PREF_CONTRAST) === '1';
$debug.checked    = localStorage.getItem(PREF_DEBUG) === '1';
document.documentElement.classList.toggle('high-contrast', $contrast.checked);

$contrast.addEventListener('change', () => {
  localStorage.setItem(PREF_CONTRAST, $contrast.checked ? '1' : '0');
  document.documentElement.classList.toggle('high-contrast', $contrast.checked);
});
$debug.addEventListener('change', () => {
  localStorage.setItem(PREF_DEBUG, $debug.checked ? '1' : '0');
});

renderSession();
renderPortal();
renderClaims();
