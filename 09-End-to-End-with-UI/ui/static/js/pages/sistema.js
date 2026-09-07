// sistema.js — dashboard dos componentes AWS.
import { api } from '../api.js';
import { requireAuth } from '../auth.js';
import { mountLayout } from '../layout.js';
import { obs } from '../util/obs-links.js';

requireAuth();
mountLayout({ active: 'sistema', title: 'Componentes' });
obs.init().catch(() => {});  // load /api/config/public into helper cache

const $summary  = document.getElementById('summary-grid');
const $cognito  = document.getElementById('card-cognito');
const $gateway  = document.getElementById('card-gateway');
const $policy   = document.getElementById('card-policy');
const $guard    = document.getElementById('card-guardrail');
const $rtBody   = document.getElementById('runtimes-body');
const $rtCount  = document.getElementById('runtimes-count');

document.getElementById('refresh-btn').addEventListener('click', load);

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function dot(ok)  { return `<span class="status-dot ${ok ? 'status-dot-success' : 'status-dot-danger'}"></span>`; }
function kv(k, v) { return `<div class="kv"><span class="kv-k">${escapeHtml(k)}</span><span class="kv-v mono">${escapeHtml(v ?? '—')}</span></div>`; }

function cardHeader(title, ok) {
  return `
    <div class="card-header">
      <div class="card-title">${dot(ok)}${escapeHtml(title)}</div>
      <span class="badge ${ok ? 'badge-success' : 'badge-danger'}">${ok ? 'OK' : 'FAIL'}</span>
    </div>
  `;
}

function renderCognito(c) {
  $cognito.innerHTML = cardHeader('Cognito', c?.ok) + `
    <div class="card-body">
      ${kv('User Pool ID', c?.poolId)}
      ${kv('Pool Name',    c?.poolName)}
      ${kv('Client ID',    c?.clientId)}
      ${kv('Grupos',       (c?.groups || []).join(', '))}
      ${c?.error ? `<div class="error-line">${escapeHtml(c.error)}</div>` : ''}
    </div>
  `;
}
function renderGateway(g) {
  $gateway.innerHTML = cardHeader('MCP Gateway', g?.ok) + `
    <div class="card-body">
      ${kv('ID',           g?.id)}
      ${kv('URL',          g?.url)}
      ${kv('Status',       g?.status)}
      ${kv('Search Type',  g?.searchType)}
      ${kv('Policy Engine', (g?.policyEngine?.type) || '—')}
      ${g?.error ? `<div class="error-line">${escapeHtml(g.error)}</div>` : ''}
    </div>
  `;
}
function renderPolicy(p) {
  const list = (p?.policies || []).map(x => {
    const policyName = x.name || '';
    let linkHtml = '';
    if (obs.cfg && policyName) {
      // Cedar Logs Insights query in aws/spans, filtered by policy name in
      // the determining_policies array. Metrics with `Policy` dimension
      // exist in the schema but are not populated (Cedar only emits per-
      // tool metrics, not per-policy). Spans are the per-policy ground truth.
      const href = obs.cwInsights({
        logGroup: 'aws/spans',
        query:    obs.queries.cedarAction(policyName),
        hours:    24,
      });
      linkHtml = `<a class="policy-link" href="${href}" target="_blank" rel="noopener" title="CloudWatch Logs Insights — spans Cedar com determining_policies = ${policyName}">enforcement ↗</a>`;
    }
    return `
      <div class="policy-row">
        <span class="mono">${escapeHtml(policyName)}</span>
        <span class="badge ${x.status === 'CREATE_COMPLETE' ? 'badge-success' : ''}">${escapeHtml(x.status || '—')}</span>
        ${linkHtml}
      </div>
    `;
  }).join('');
  $policy.innerHTML = cardHeader('Policy Engine (Cedar)', p?.ok) + `
    <div class="card-body">
      ${kv('ID',       p?.id)}
      ${kv('Policies', String(p?.count ?? 0))}
      <div class="policy-list">${list || '<div class="muted">nenhuma policy</div>'}</div>
      ${p?.error ? `<div class="error-line">${escapeHtml(p.error)}</div>` : ''}
    </div>
  `;
}
function renderGuardrail(g) {
  $guard.innerHTML = cardHeader('Bedrock Guardrail', g?.ok) + `
    <div class="card-body">
      ${kv('ID',      g?.id)}
      ${kv('Versão',  g?.version)}
    </div>
  `;
}

function renderRuntimes(list) {
  $rtCount.textContent = `${list.length} runtimes`;
  if (!list.length) { $rtBody.innerHTML = '<div class="governance-empty">nenhum runtime configurado</div>'; return; }
  $rtBody.innerHTML = `
    <div class="rt-grid">
      ${list.map(r => `
        <div class="rt-card">
          <div class="rt-head">
            ${dot(r.ok)}
            <strong>${escapeHtml(r.name)}</strong>
            <span class="badge ${r.ok ? 'badge-success' : 'badge-danger'}">${escapeHtml(r.status || 'unknown')}</span>
          </div>
          <div class="rt-body">
            <div class="kv"><span class="kv-k">ID</span><span class="kv-v mono">${escapeHtml(r.id || '—')}</span></div>
            <div class="kv"><span class="kv-k">ARN</span><span class="kv-v mono ellipsis" title="${escapeHtml(r.arn || '')}">${escapeHtml((r.arn || '').split(':').pop() || '—')}</span></div>
            ${r.error ? `<div class="error-line">${escapeHtml(r.error)}</div>` : ''}
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

async function load() {
  $summary.innerHTML = `<div class="metric-card"><div class="metric-label">Carregando status…</div></div>`;
  try {
    const data = await api.get('/api/system/status');
    const readyRt = (data.runtimes || []).filter(r => r.ok).length;
    const totalRt = (data.runtimes || []).length;
    const allOk = data.cognito?.ok && data.gateway?.ok && data.policyEngine?.ok && data.guardrail?.ok && (readyRt === totalRt);
    $summary.innerHTML = `
      <div class="metric-card">
        <div class="metric-label">Região</div>
        <div class="metric-value mono">${escapeHtml(data.region)}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Setor</div>
        <div class="metric-value">${escapeHtml(data.sector)}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Runtimes READY</div>
        <div class="metric-value">${readyRt}<span class="muted"> / ${totalRt}</span></div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Saúde geral</div>
        <div class="metric-value ${allOk ? 'text-permit' : 'text-deny'}">${allOk ? 'OK' : 'Atenção'}</div>
      </div>
    `;
    renderCognito(data.cognito);
    renderGateway(data.gateway);
    renderPolicy(data.policyEngine);
    renderGuardrail(data.guardrail);
    renderRuntimes(data.runtimes || []);
  } catch (e) {
    $summary.innerHTML = `<div class="error-line">Falha ao carregar status: ${escapeHtml(e.message)}</div>`;
  }
}

load();
