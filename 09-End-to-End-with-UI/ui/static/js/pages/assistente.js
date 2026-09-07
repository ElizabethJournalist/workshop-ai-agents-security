// pages/assistente.js — chat console controller.

import { requireAuth, getToken, getSession } from '../auth.js';
import { mountLayout } from '../layout.js';
import { obs } from '../util/obs-links.js';

requireAuth();
mountLayout({ active: 'assistente', title: 'Assistente' });
obs.init().catch(() => {});  // load /api/config/public into helper cache

const AGENTS = [
  { key: 'SmartAgent',            label: 'Automático',           hint: 'roteia para o especialista certo' },
  { key: 'GridMonitorAgent',      label: 'Grid',                 hint: 'rede, blackout, setores' },
  { key: 'MaintenanceAgent',      label: 'Manutenção',           hint: 'ordens, aprovações, ativos' },
  { key: 'ContractAgent',         label: 'Contratos',            hint: 'cláusulas, buscas' },
  { key: 'CustomerBillingAgent',  label: 'Faturamento',          hint: 'faturas, cobranças (restrito)' },
  { key: 'RegulatoryReportAgent', label: 'Regulatório',          hint: 'relatórios ANEEL' },
];

const SUGGESTIONS = {
  SmartAgent: [
    'Qual o status da rede no setor norte?',
    'Crie uma ordem de manutenção para o TR-042',
    'Gere o relatório de conformidade Q1-2024',
  ],
  GridMonitorAgent: [
    'Qual o status atual do setor leste?',
    'Mostre alertas ativos na rede',
  ],
  MaintenanceAgent: [
    'Aprove a ordem WO-2024-0892',
    'Crie uma ordem para o transformador TR-042',
    'Histórico do ativo SE-LESTE-03',
  ],
  ContractAgent: [
    'Busque contratos vigentes com fornecedor XYZ',
    'Extraia cláusula de penalidade',
  ],
  CustomerBillingAgent: [
    'Mostre a fatura INV-2024-03-0091',
    'Saldo do cliente C-10042',
  ],
  RegulatoryReportAgent: [
    'Gere relatório Q1-2024',
    'Submeta RPT-2024-Q1 à ANEEL',
  ],
};

let currentAgent = 'SmartAgent';
const decisions  = [];          // in-memory governance trail for this session

// Chat session id — created by the backend on login and returned in the
// session payload. One session per login: logout + login = new conversation.
// Cross-session LTM still works because Memory namespace uses actor_id
// (Cognito sub), not session_id.
const CHAT_SESSION_ID = getSession()?.session_id || '';

// Conversation history for multi-turn context (sent to SmartAgent each turn).
// Stores last 6 turns as {role, content} — only for SmartAgent (specialists
// are single-turn by design and have their own STM via session manager).
const conversationHistory = [];

// ───────── rendering ─────────────────────────────────────────────────────

const selectorEl    = document.getElementById('agent-selector');
const suggestionsEl = document.getElementById('suggestions');
const logEl         = document.getElementById('log');
const emptyStateEl  = document.getElementById('empty-state');
const composerEl    = document.getElementById('composer');
const inputEl       = document.getElementById('composer-input');
const sendBtn       = document.getElementById('send-btn');
const panelEl       = document.getElementById('governance-panel');

function renderSelector() {
  selectorEl.innerHTML = AGENTS.map(a => `
    <button type="button" class="agent-pill ${a.key === currentAgent ? 'active' : ''}" data-key="${a.key}" title="${a.hint}">
      <span class="dot"></span>
      <span>${a.label}</span>
    </button>
  `).join('');
  selectorEl.querySelectorAll('.agent-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      currentAgent = btn.dataset.key;
      renderSelector();
      renderSuggestions();
    });
  });
}

function renderSuggestions() {
  const sugs = SUGGESTIONS[currentAgent] || [];
  suggestionsEl.innerHTML = sugs.map(s => `<button class="composer-suggestion" type="button">${s}</button>`).join('');
  suggestionsEl.querySelectorAll('button').forEach((b, i) => {
    b.addEventListener('click', () => { inputEl.value = sugs[i]; inputEl.focus(); });
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function addTurn({ role, agent, content, thinking = false }) {
  if (emptyStateEl && emptyStateEl.parentNode) emptyStateEl.remove();

  const wrap = document.createElement('div');
  wrap.className = `turn turn-${role === 'user' ? 'user' : 'agent'}`;
  const meta = role === 'user'
    ? 'VOCÊ'
    : `<span class="mono">${escapeHtml(agent || 'AGENTE')}</span>`;
  wrap.innerHTML = `
    <div class="turn-meta">${meta}</div>
    <div class="turn-content">${
      thinking
        ? '<div class="thinking"><span></span><span></span><span></span></div>'
        : escapeHtml(content).replace(/\n/g, '<br>')
    }</div>
  `;
  logEl.appendChild(wrap);
  logEl.scrollTop = logEl.scrollHeight;
  return wrap;
}

function addGovernanceBadges(turnEl, { agent, governance }) {
  const badge = document.createElement('div');
  badge.className = 'turn-badges';
  const verdict = governance?.verdict || 'unknown';
  const label = {
    'permit':         ['PERMIT', 'badge-success'],
    'deny':           ['DENY',   'badge-danger'],
    'mixed':          ['MIXED',  'badge-warning'],
    'cedar-filtered': ['CEDAR BLOCKED', 'badge-danger'],
    'not-invoked':    ['NO TOOLS', 'badge-info'],
  }[verdict] || ['?', ''];
  badge.innerHTML = `
    <span class="badge ${label[1]}">${label[0]}</span>
    <span class="badge">${escapeHtml(agent)}</span>
  `;
  turnEl.appendChild(badge);
}

function addObsLinks(turnEl, { sessionId, agent, governance }) {
  if (!obs.cfg) return;  // helper not initialized yet
  const verdict = governance?.verdict;
  const dels = governance?.delegations || [];
  // Pick the specialist runtime log group: prefer the agent that actually
  // ran (from delegations); otherwise fall back to the routing agent.
  const specialistName = (dels[0]?.agent_name) || agent || 'SmartAgent';
  const specialistLog = obs.cfg.logGroups.runtimes[specialistName] || obs.cfg.logGroups.runtimes['SmartAgent'];

  const links = [];

  // 🔍 Logs of this session (specialist runtime) — query filtered by session_id
  if (specialistLog && sessionId) {
    links.push({
      icon: '🔍',
      label: 'Logs desta sessão',
      title: `CloudWatch Logs Insights — ${specialistName} runtime, filtrado por session_id`,
      href: obs.cwInsights({
        logGroup: specialistLog,
        query: obs.queries.bySession(sessionId),
        hours: 3,
      }),
    });
  }

  // 🛡️ Cedar — DENY decisions in aws/spans (the real source).
  // Cedar publishes structured spans named AgentCore.Policy.AuthorizeAction
  // with attributes.aws.agentcore.policy.authorization_decision = ALLOW|DENY.
  // CloudWatch Metrics are good for aggregates; aws/spans tells the per-call story.
  if (verdict !== 'not-invoked') {
    const denyOnly = verdict === 'deny' || verdict === 'mixed' || verdict === 'cedar-filtered';
    links.push({
      icon: '🛡️',
      label: denyOnly ? 'Cedar DENY spans' : 'Cedar spans',
      title: denyOnly
        ? 'Spans de Cedar com authorization_decision = DENY'
        : 'Todos os spans de Cedar (AuthorizeAction + PartiallyAuthorizeActions)',
      href: obs.cwInsights({
        logGroup: 'aws/spans',
        query: denyOnly ? obs.queries.cedarDeny() : obs.queries.cedarAll(),
        hours: 3,
      }),
    });
  }

  // 📊 Traces (OTel spans) — log group aws/spans has end-to-end trace data
  // even when X-Ray ServiceLens is empty.
  links.push({
    icon: '📊',
    label: 'Traces',
    title: 'OTel spans do bedrock-agentcore (log group aws/spans)',
    href: obs.cwInsights({
      logGroup: 'aws/spans',
      query: obs.queries.spansBySpecialist(specialistName),
      hours: 3,
    }),
  });

  if (!links.length) return;

  const bar = document.createElement('div');
  bar.className = 'turn-obs-links';
  bar.innerHTML = links.map(l => `
    <a class="obs-link" href="${l.href}" target="_blank" rel="noopener" title="${escapeHtml(l.title)}">
      ${l.icon} <span>${l.label}</span>
    </a>
  `).join('');
  turnEl.appendChild(bar);
}

function renderGovernancePanel() {
  if (!decisions.length) {
    panelEl.innerHTML = '<div class="governance-empty">Envie uma mensagem para ver as decisões de governança.</div>';
    return;
  }
  panelEl.innerHTML = decisions.slice().reverse().map(d => {
    const g = d.governance || {};
    const dels = g.delegations || [];
    const verdictMap = {
      'permit':         ['PERMIT', 'badge-success'],
      'deny':           ['DENY',   'badge-danger'],
      'mixed':          ['MIXED',  'badge-warning'],
      'cedar-filtered': ['CEDAR',  'badge-danger'],
      'not-invoked':    ['—',      'badge-info'],
    };
    const [vLabel, vClass] = verdictMap[g.verdict] || ['?', ''];
    return `
      <div class="governance-item">
        <div class="governance-item-head">
          <span class="governance-item-agent">${escapeHtml(d.agent)}</span>
          <span class="badge ${vClass}">${vLabel}</span>
        </div>
        <div class="governance-item-time">${d.time}</div>
        ${dels.map(deleg => {
          const calls = deleg.tools_called || [];
          const denied = deleg.denied_by_cedar || [];
          return `
            <div class="cedar-block">
              <div class="cedar-specialist">${escapeHtml(deleg.agent_name || '?')}</div>
              ${calls.length ? `
                <div class="cedar-line">
                  <span class="muted">tools chamadas:</span>
                  ${calls.map(c => `
                    <span class="mono ${c.decision === 'deny' ? 'text-deny' : 'text-permit'}">
                      ${escapeHtml(c.name)} · ${c.decision.toUpperCase()}
                    </span>
                  `).join(' ')}
                </div>
              ` : ''}
              ${denied.length ? `
                <div class="cedar-line">
                  <span class="muted">Cedar bloqueou:</span>
                  ${denied.map(t => `<span class="mono text-deny">${escapeHtml(t)}</span>`).join(' ')}
                </div>
              ` : ''}
              ${!calls.length && !denied.length ? `
                <div class="cedar-line muted">sem decisões Cedar (resposta conversacional)</div>
              ` : ''}
            </div>
          `;
        }).join('')}
      </div>
    `;
  }).join('');
}

// ───────── send ──────────────────────────────────────────────────────────

async function send(prompt) {
  inputEl.disabled = true;
  sendBtn.disabled = true;
  sendBtn.textContent = 'Enviando…';

  addTurn({ role: 'user', content: prompt });
  const placeholder = addTurn({ role: 'agent', agent: currentAgent, thinking: true });
  const contentEl = placeholder.querySelector('.turn-content');

  let accumulated = '';
  let finalAgent  = currentAgent;
  let finalGovernance = null;
  let finalSessionId  = CHAT_SESSION_ID;
  let gotFirstChunk   = false;

  const renderBody = () => {
    contentEl.innerHTML = escapeHtml(accumulated).replace(/\n/g, '<br>');
    logEl.scrollTop = logEl.scrollHeight;
  };

  try {
    const token = getToken();
    const resp = await fetch('/api/agent/invoke', {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        agent:      currentAgent,
        prompt,
        session_id: CHAT_SESSION_ID,
        // Only send history for SmartAgent — specialists are single-turn.
        history: currentAgent === 'SmartAgent' ? conversationHistory.slice(-6) : [],
      }),
    });
    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${detail.slice(0, 200)}`);
    }

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are delimited by "\n\n". Split and process each.
      let sep;
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);

        for (const line of raw.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          let ev;
          try { ev = JSON.parse(line.slice(6)); }
          catch { continue; }

          if (ev.type === 'delta') {
            if (!gotFirstChunk) {
              gotFirstChunk = true;
              contentEl.innerHTML = '';
            }
            accumulated += ev.text || '';
            renderBody();
          } else if (ev.type === 'done') {
            finalAgent       = ev.agent || finalAgent;
            finalGovernance  = ev.governance || null;
            finalSessionId   = ev.session_id || finalSessionId;
            if (!gotFirstChunk && ev.response) {
              accumulated = ev.response;
              contentEl.innerHTML = '';
              renderBody();
            }
          } else if (ev.type === 'error') {
            throw new Error(ev.message || 'stream error');
          }
          // tool_start / tool_end: intentionally ignored for a clean chat UX —
          // the delegation evidence is captured in the governance panel and
          // in CloudWatch (aws/spans + gateway logs).
        }
      }
    }

    // If we never got any text (edge case), keep whatever the done event had.
    if (!accumulated) {
      contentEl.innerHTML = '<span class="muted">(resposta vazia)</span>';
    }

    if (finalGovernance) {
      addGovernanceBadges(placeholder, { agent: finalAgent, governance: finalGovernance });
      addObsLinks(placeholder, {
        sessionId: finalSessionId,
        agent: finalAgent,
        governance: finalGovernance,
      });
      decisions.push({
        time:       new Date().toLocaleTimeString('pt-BR'),
        agent:      finalAgent,
        prompt,
        response:   accumulated,
        governance: finalGovernance,
      });
      renderGovernancePanel();
    }

    // Record this turn in history (SmartAgent only — for multi-turn context).
    if (currentAgent === 'SmartAgent' && accumulated) {
      conversationHistory.push({ role: 'user',      content: prompt });
      conversationHistory.push({ role: 'assistant', content: accumulated });
      // Keep at most 12 entries (6 turns) to limit token usage.
      if (conversationHistory.length > 12) conversationHistory.splice(0, conversationHistory.length - 12);
    }
  } catch (err) {
    contentEl.innerHTML =
      `<span style="color: var(--state-danger-fg)">Erro: ${escapeHtml(err.message)}</span>`;
  } finally {
    inputEl.disabled = false;
    sendBtn.disabled = false;
    sendBtn.textContent = 'Enviar';
    inputEl.value = '';
    inputEl.focus();
  }
}

composerEl.addEventListener('submit', (e) => {
  e.preventDefault();
  const v = inputEl.value.trim();
  if (!v) return;
  // Clear the input right away so the user sees their message appear in the
  // log and gets a clean textarea while the response is streaming in.
  inputEl.value = '';
  inputEl.style.height = 'auto';
  send(v);
});

inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    composerEl.requestSubmit();
  }
});

// Autogrow textarea
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(160, inputEl.scrollHeight) + 'px';
});

// ───────── init ──────────────────────────────────────────────────────────

renderSelector();
renderSuggestions();
inputEl.focus();
