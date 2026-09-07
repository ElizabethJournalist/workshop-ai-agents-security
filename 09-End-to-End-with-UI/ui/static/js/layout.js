// layout.js — renders the shared sidebar and topbar on every internal page.
// Call `mountLayout({ active, title })` at the top of each page controller.

import { getUser, logout } from './auth.js';

const NAV = [
  { group: 'Agentes',         items: [
    { key: 'assistente',   label: 'Assistente',    href: '/assistente',    icon: 'message-square' },
  ]},
  { group: 'Monitoramento',   items: [
    { key: 'governanca',   label: 'Governança',    href: '/governanca',    icon: 'shield-check' },
  ]},
  { group: 'Sistema',         items: [
    { key: 'sistema',        label: 'Componentes',     href: '/sistema',        icon: 'layers' },
    { key: 'configuracoes',  label: 'Configurações',   href: '/configuracoes',  icon: 'settings' },
  ]},
];

const ICONS = {
  'message-square': '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  'shield-check':   '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>',
  'layers':         '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
  'settings':       '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
};

function icon(name) {
  const path = ICONS[name] || '';
  return `<svg class="nav-item-icon" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}

function avatarInitial(email) {
  return (email || '?').trim().charAt(0).toUpperCase();
}

export function mountLayout({ active, title }) {
  const user = getUser();
  if (!user) { window.location.href = '/'; return; }

  // Sidebar
  const sidebar = document.querySelector('.sidebar');
  if (sidebar) {
    sidebar.innerHTML = `
      <div class="sidebar-brand">
        <div class="sidebar-brand-mark">AG</div>
        <div>
          <div>Governança</div>
          <div class="text-xs muted">AgentCore · Demo</div>
        </div>
      </div>

      ${NAV.map(sec => `
        <div class="nav-section">${sec.group}</div>
        <div class="nav-list">
          ${sec.items.map(it => `
            <a class="nav-item ${active === it.key ? 'active' : ''}" href="${it.href}">
              ${icon(it.icon)}
              <span>${it.label}</span>
            </a>
          `).join('')}
        </div>
      `).join('')}

      <div class="sidebar-footer">
        <div>Região <span class="mono">us-east-1</span></div>
        <div>Setor <span class="mono">utility</span></div>
      </div>
    `;
  }

  // Topbar
  const topbar = document.querySelector('.topbar');
  if (topbar) {
    const groupsStr = (user.groups || []).join(', ') || '—';
    topbar.innerHTML = `
      <div class="topbar-title">${title || ''}</div>
      <div class="topbar-actions">
        <div class="user-chip" title="Sessão ativa">
          <div class="user-chip-avatar">${avatarInitial(user.email)}</div>
          <div>
            <div>${user.email}</div>
            <div class="user-chip-groups">grupo: ${groupsStr}</div>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" id="logout-btn">Sair</button>
      </div>
    `;
    document.getElementById('logout-btn').addEventListener('click', () => logout());
  }
}
