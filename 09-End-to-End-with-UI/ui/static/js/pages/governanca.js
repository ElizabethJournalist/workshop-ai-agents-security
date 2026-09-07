// governanca.js — consumes native AgentCore Policy Engine metrics from
// CloudWatch (namespace AWS/Bedrock-AgentCore). Zero derivation.
import { api } from '../api.js';
import { requireAuth } from '../auth.js';
import { mountLayout } from '../layout.js';
import { obs } from '../util/obs-links.js';

requireAuth();
mountLayout({ active: 'governanca', title: 'Governança' });

const REGION = 'us-east-1';

const $summary    = document.getElementById('summary');
const $windowSel  = document.getElementById('window');
const $windowLbl  = document.getElementById('window-label');
const $refresh    = document.getElementById('refresh');
const $cwLink     = document.getElementById('cw-link');
const $toolsBody  = document.getElementById('tools-body');
const $toolsCount = document.getElementById('tools-count');
const $chart      = document.getElementById('chart');
const $engineId   = document.getElementById('engine-id');
const $genaiLink  = document.getElementById('genai-link');
const $spansLink  = document.getElementById('spans-link');

$refresh.addEventListener('click', load);
$windowSel.addEventListener('change', load);

$genaiLink.href = `https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#gen-ai-observability/agent-core`;
$spansLink.href = `https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#logsV2:log-groups/log-group/aws$252Fspans`;

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function fmt(n) {
  if (n >= 1000) return (n / 1000).toFixed(1).replace('.0', '') + 'k';
  return String(Math.round(n));
}

function renderSummary(data) {
  const t = data.totals;
  const total = (t.allow || 0) + (t.deny || 0);
  const denyPct = total > 0 ? Math.round((t.deny / total) * 100) : 0;
  $summary.innerHTML = `
    <div class="metric-card">
      <div class="metric-label">Allow</div>
      <div class="metric-value text-permit">${fmt(t.allow)}</div>
      <div class="metric-sub">decisões permitidas</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Deny</div>
      <div class="metric-value text-deny">${fmt(t.deny)}</div>
      <div class="metric-sub">${denyPct}% do total</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Total avaliado</div>
      <div class="metric-value">${fmt(total)}</div>
      <div class="metric-sub">allow + deny</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Mismatch</div>
      <div class="metric-value">${fmt(t.mismatch)}</div>
      <div class="metric-sub">atributo faltante / tipo inválido</div>
    </div>
  `;
}

function renderTools(rows) {
  $toolsCount.textContent = `${rows.length} tools`;
  if (!rows.length) {
    $toolsBody.innerHTML = '<div class="governance-empty">Sem decisões no período selecionado.</div>';
    return;
  }
  const max = Math.max(...rows.map(r => (r.allow || 0) + (r.deny || 0)));
  $toolsBody.innerHTML = `
    <table class="table tools-table">
      <thead>
        <tr>
          <th>Tool</th>
          <th class="right">Allow</th>
          <th class="right">Deny</th>
          <th>Distribuição</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(r => {
          const allow = r.allow || 0;
          const deny  = r.deny  || 0;
          const totalW = max > 0 ? 100 : 0;
          const aW = max > 0 ? (allow / max) * 100 : 0;
          const dW = max > 0 ? (deny  / max) * 100 : 0;
          return `
            <tr>
              <td class="mono">${escapeHtml(r.tool)}</td>
              <td class="right mono text-permit">${fmt(allow)}</td>
              <td class="right mono text-deny">${fmt(deny)}</td>
              <td>
                <div class="bar" style="width:${totalW}%">
                  ${allow ? `<div class="bar-allow" style="width:${aW}%" title="Allow ${allow}"></div>` : ''}
                  ${deny  ? `<div class="bar-deny"  style="width:${dW}%" title="Deny ${deny}"></div>`   : ''}
                </div>
              </td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;
}

function renderChart(allowTs, denyTs) {
  const ctx = $chart.getContext('2d');
  const W = $chart.width  = $chart.clientWidth;
  const H = $chart.height = 180;
  ctx.clearRect(0, 0, W, H);

  const merged = [];
  const byT = new Map();
  [...allowTs, ...denyTs].forEach(p => { byT.set(p.t, true); });
  const times = [...byT.keys()].sort();
  if (!times.length) {
    ctx.fillStyle = 'rgba(100,116,139,0.8)';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('Sem dados no período.', W / 2, H / 2);
    return;
  }
  const a = new Map(allowTs.map(p => [p.t, p.v]));
  const d = new Map(denyTs.map(p => [p.t, p.v]));
  const ys = times.map(t => Math.max(a.get(t) || 0, d.get(t) || 0));
  const maxY = Math.max(1, ...ys);

  const pad = { t: 10, r: 10, b: 24, l: 30 };
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;

  // axes
  ctx.strokeStyle = 'rgba(148,163,184,0.3)';
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t);
  ctx.lineTo(pad.l, H - pad.b);
  ctx.lineTo(W - pad.r, H - pad.b);
  ctx.stroke();

  // y ticks
  ctx.fillStyle = 'rgba(100,116,139,0.9)';
  ctx.font = '10px system-ui';
  ctx.textAlign = 'right';
  [0, 0.5, 1].forEach(f => {
    const y = pad.t + plotH * (1 - f);
    ctx.fillText(Math.round(maxY * f), pad.l - 4, y + 3);
    ctx.strokeStyle = 'rgba(148,163,184,0.15)';
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(W - pad.r, y);
    ctx.stroke();
  });

  function line(map, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    times.forEach((t, i) => {
      const x = pad.l + (i / Math.max(1, times.length - 1)) * plotW;
      const y = pad.t + plotH * (1 - ((map.get(t) || 0) / maxY));
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = color;
    times.forEach((t, i) => {
      const x = pad.l + (i / Math.max(1, times.length - 1)) * plotW;
      const y = pad.t + plotH * (1 - ((map.get(t) || 0) / maxY));
      ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2); ctx.fill();
    });
  }
  line(a, 'var(--state-success-fg)'); // will fall back as color str
  // canvas doesn't resolve CSS vars — use literal colors:
  ctx.strokeStyle = '#047857'; ctx.fillStyle = '#047857';
  line(a, '#047857');
  line(d, '#B91C1C');

  // legend
  ctx.textAlign = 'left';
  ctx.font = '11px system-ui';
  ctx.fillStyle = '#047857';
  ctx.fillText('● Allow', pad.l + 4, pad.t + 12);
  ctx.fillStyle = '#B91C1C';
  ctx.fillText('● Deny', pad.l + 60, pad.t + 12);
}

const $obsShortcuts = document.getElementById('obs-shortcuts');

async function renderShortcuts(hours) {
  if (!$obsShortcuts) return;
  let cfg;
  try { cfg = await obs.init(); } catch { cfg = null; }
  if (!cfg) {
    $obsShortcuts.innerHTML = '<div class="governance-empty">Configuração de observabilidade indisponível.</div>';
    return;
  }

  const cards = [
    {
      icon:  '🤖',
      title: 'SmartAgent runtime',
      desc:  'Logs do agente roteador — ver delegações, prompts, respostas.',
      href:  obs.cwInsights({
        logGroup: cfg.logGroups.runtimes['SmartAgent'],
        query:    obs.queries.bySession(''),
        hours,
      }),
      cta: 'Abrir Logs Insights',
    },
    {
      icon:  '🟢',
      title: 'Cedar — Allow por tool',
      desc:  'AllowDecisions de todas as 13 tools (cobre P0..P8, exceto P6 que é deny universal).',
      href:  obs.cedarMetrics('AllowDecisions'),
      cta: 'Ver gráfico Allow',
    },
    {
      icon:  '🔴',
      title: 'Cedar — Deny por tool',
      desc:  'DenyDecisions de todas as 13 tools. P6 (submit_to_regulator) é universal; P3 (approve operator) e P8 (priority=high sem manager) aparecem aqui.',
      href:  obs.cedarMetrics('DenyDecisions'),
      cta: 'Ver gráfico Deny',
    },
    {
      icon:  '🧾',
      title: 'Cedar — spans (decisões)',
      desc:  'Cada chamada AuthorizeAction com policy.authorization_decision (ALLOW/DENY) e determining_policies.',
      href:  obs.cwInsights({
        logGroup: 'aws/spans',
        query:    obs.queries.cedarAll(),
        hours,
      }),
      cta: 'Ver decisões Cedar',
    },
    {
      icon:  '⚡',
      title: 'Lambdas (5 tools)',
      desc:  'Invocações das ferramentas: duração, erros, X-Ray trace IDs.',
      href:  obs.cwInsights({
        logGroup: cfg.logGroups.lambdas[0] || '',
        query:    obs.queries.lambdaInvocations(),
        hours,
      }),
      cta: 'Logs do grid_api',
    },
    {
      icon:  '📊',
      title: 'Traces (OTel spans)',
      desc:  'Spans end-to-end no log group aws/spans (alimenta X-Ray ServiceLens).',
      href:  obs.cwInsights({
        logGroup: 'aws/spans',
        query:    obs.queries.spansBySpecialist(''),
        hours,
      }),
      cta: 'Ver spans recentes',
    },
    {
      icon:  '🚦',
      title: 'Guardrail — intervenções',
      desc:  'Bedrock Guardrails bloqueando entrada/saída (finish_reason=guardrail_intervened). DISTINTO do Cedar.',
      href:  obs.cwInsights({
        logGroup: cfg.logGroups.runtimes['SmartAgent'],
        query:    obs.queries.guardrail(),
        hours,
      }),
      cta: 'Ver intervenções',
    },
    {
      icon:  '📋',
      title: 'CloudTrail — bedrock-agentcore',
      desc:  'Operações de management capturadas: ListGateways, ListAgentRuntimes, etc.',
      href:  obs.cloudtrailBySource('bedrock-agentcore.amazonaws.com'),
      cta: 'Abrir CloudTrail',
    },
  ];

  $obsShortcuts.innerHTML = cards.map(c => `
    <a class="obs-shortcut" href="${c.href}" target="_blank" rel="noopener" title="${escapeHtml(c.desc)}">
      <div class="obs-shortcut-head">
        <span class="obs-shortcut-icon">${c.icon}</span>
        <span class="obs-shortcut-title">${escapeHtml(c.title)}</span>
      </div>
      <div class="obs-shortcut-desc">${escapeHtml(c.desc)}</div>
      <div class="obs-shortcut-cta">${escapeHtml(c.cta)} ↗</div>
    </a>
  `).join('');
}

const $cedarBody  = document.getElementById('cedar-body');
const $cedarCount = document.getElementById('cedar-count');
const $traceModal      = document.getElementById('trace-modal');
const $traceModalBody  = document.getElementById('trace-modal-body');
const $traceModalClose = document.getElementById('trace-modal-close');
const $traceModalOverlay = document.getElementById('trace-modal-overlay');

async function renderCedarDecisions(hours) {
  if (!$cedarBody) return;
  $cedarBody.innerHTML = '<div class="governance-empty">Carregando decisões Cedar…</div>';
  try {
    const data = await api.get(`/api/governance/cedar-decisions?hours=${hours}`);
    const ds = data.decisions || [];
    $cedarCount.textContent = `${data.totals?.allow || 0} ALLOW, ${data.totals?.deny || 0} DENY · ${ds.length} spans`;

    if (!ds.length) {
      $cedarBody.innerHTML = '<div class="governance-empty">Nenhuma decisão Cedar nas últimas ' + hours + 'h.</div>';
      return;
    }

    const rows = ds.map(d => {
      const decision = d.decision || '?';
      const cls = decision === 'ALLOW' ? 'badge-success'
                : decision === 'DENY'  ? 'badge-danger'
                : decision === 'MIXED' ? 'badge-warning' : '';
      const isPart = d.name === 'PartiallyAuthorizeActions';
      const detail = isPart
        ? `${d.allowed_count || 0} allow · ${d.denied_count || 0} deny`
        : (d.determining_policies || []).join(', ') || '—';
      return `
        <tr class="cedar-row" data-trace="${escapeHtml(d.traceId || '')}">
          <td class="mono small">${escapeHtml((d.timestamp || '').slice(11, 19))}</td>
          <td><span class="badge ${cls}">${escapeHtml(decision)}</span></td>
          <td class="mono small">${escapeHtml(d.name || '?')}</td>
          <td class="small">${escapeHtml(detail)}</td>
          <td class="mono small">${escapeHtml((d.traceId || '').slice(0, 16))}…</td>
          <td><button class="btn btn-ghost btn-sm" data-trace="${escapeHtml(d.traceId || '')}">drill-down</button></td>
        </tr>`;
    }).join('');

    $cedarBody.innerHTML = `
      <table class="cedar-table">
        <thead>
          <tr>
            <th>Hora</th>
            <th>Decisão</th>
            <th>Tipo</th>
            <th>Detalhe</th>
            <th>Trace</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;

    // Wire drill-down clicks
    $cedarBody.querySelectorAll('button[data-trace]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const trace = e.target.getAttribute('data-trace');
        if (trace) openTraceModal(trace);
      });
    });
  } catch (err) {
    $cedarBody.innerHTML = `<div class="governance-empty" style="color:var(--state-danger-fg)">Erro: ${escapeHtml(err.message)}</div>`;
  }
}

async function openTraceModal(traceId) {
  $traceModal.hidden = false;
  $traceModalBody.innerHTML = '<div class="governance-empty">Carregando trace…</div>';
  try {
    const data = await api.get(`/api/governance/trace/${encodeURIComponent(traceId)}`);
    const cedars = (data.cedar_decisions || []).map(d => {
      if (d.type === 'AuthorizeAction') {
        const cls = d.decision === 'ALLOW' ? 'badge-success' : 'badge-danger';
        return `<div class="trace-row">
          <span class="badge ${cls}">${escapeHtml(d.decision || '?')}</span>
          <span class="mono small">${escapeHtml(d.type)}</span>
          <span class="small">policies: ${escapeHtml((d.determining_policies || []).join(', '))}</span>
        </div>`;
      } else {
        return `<div class="trace-row">
          <span class="badge badge-warning">FILTER</span>
          <span class="mono small">${escapeHtml(d.type)}</span>
          <span class="small">${(d.allowed_tools || []).length} allow · ${(d.denied_tools || []).length} deny</span>
        </div>
        ${(d.denied_tools || []).length ? `<div class="trace-detail">denied: <span class="mono small">${escapeHtml((d.denied_tools || []).join(', '))}</span></div>` : ''}`;
      }
    }).join('');

    const tools = (data.tool_calls || []).map(t =>
      `<div class="trace-row"><span class="mono small">${escapeHtml(t.tool)}</span></div>`
    ).join('') || '<div class="governance-empty small">(nenhuma tool foi chamada)</div>';

    $traceModalBody.innerHTML = `
      <div class="trace-section">
        <div class="trace-label">Sessão</div>
        <div class="mono small">${escapeHtml((data.session_id || '—').slice(0, 36))}</div>
      </div>
      <div class="trace-section">
        <div class="trace-label">Pergunta do usuário</div>
        <div class="trace-quote">${escapeHtml(data.user_prompt || '(não capturada)')}</div>
      </div>
      ${data.agent_response ? `
        <div class="trace-section">
          <div class="trace-label">Resposta do agente</div>
          <div class="trace-quote">${escapeHtml(data.agent_response)}</div>
        </div>` : ''}
      <div class="trace-section">
        <div class="trace-label">Decisões Cedar</div>
        ${cedars || '<div class="governance-empty small">(nenhuma)</div>'}
      </div>
      <div class="trace-section">
        <div class="trace-label">Tools chamadas no Gateway</div>
        ${tools}
      </div>
      <div class="trace-section">
        <div class="trace-label">Agentes envolvidos</div>
        <div class="small">${(data.agents_involved || []).map(a => `<span class="mono">${escapeHtml(a)}</span>`).join(' · ') || '—'}</div>
      </div>
      <div class="trace-section">
        <div class="trace-label">Trace</div>
        <div class="mono small">${escapeHtml(traceId)}</div>
        <div class="small muted">${data.spans_count || 0} spans no aws/spans</div>
      </div>
    `;
  } catch (err) {
    $traceModalBody.innerHTML = `<div class="governance-empty" style="color:var(--state-danger-fg)">Erro: ${escapeHtml(err.message)}</div>`;
  }
}

function closeTraceModal() {
  $traceModal.hidden = true;
}
$traceModalClose?.addEventListener('click', closeTraceModal);
$traceModalOverlay?.addEventListener('click', closeTraceModal);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeTraceModal(); });

async function load() {
  const hours = Number($windowSel.value);
  $windowLbl.textContent = `janela: últimas ${hours}h`;
  $summary.innerHTML     = `<div class="metric-card"><div class="metric-label">Carregando métricas do CloudWatch…</div></div>`;
  $toolsBody.innerHTML   = '<div class="governance-empty">Carregando…</div>';

  try {
    const data = await api.get(`/api/governance/metrics?hours=${hours}`);
    $engineId.textContent = data.engine || '—';
    $cwLink.href = `https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#metricsV2:graph=~();query=AWS%2FBedrock-AgentCore%20PolicyEngine%3D${encodeURIComponent(data.engine || '')}`;

    renderSummary(data);
    renderTools(data.by_tool || []);
    renderChart(data.series?.allow_ts || [], data.series?.deny_ts || []);
    await renderShortcuts(hours);
    renderCedarDecisions(hours);
  } catch (err) {
    $summary.innerHTML = `
      <div class="metric-card"><div class="metric-label" style="color:var(--state-danger-fg)">
        Falha ao ler métricas: ${escapeHtml(err.message)}
      </div></div>
    `;
  }
}

load();
window.addEventListener('resize', () => renderChart.last && renderChart.last());
