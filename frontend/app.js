import { escapeHtml } from './components/escape.js';
import { getLang, t } from './components/i18n.js';
import { mountAnalyticsView } from './views/analytics.js';
import { mountCallDetailView } from './views/call-detail.js';
import { mountCallHistoryView } from './views/call-history.js';

const appEl = document.getElementById('app');
const healthBadge = document.getElementById('healthBadge');
const langToggle = document.getElementById('langToggle');

const state = {
  view: 'workspace',
  selectedCall: null,
};

function applyLangChrome() {
  const lang = getLang();
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.getElementById('navWorkspace').textContent = t('navWorkspace');
  document.getElementById('navHistory').textContent = t('navHistory');
  document.getElementById('footLeft').textContent = t('footerLeft');
  document.getElementById('footRight').textContent = t('footerRight');
  langToggle.textContent = t('langBtn');
}

function setActiveNav(view) {
  document.querySelectorAll('.nav-links a').forEach(a => {
    a.classList.toggle('active', a.dataset.view === view);
  });
}

async function refreshHealth() {
  try {
    const resp = await fetch('/api/health');
    const h = await resp.json();
    const dotClass = h.status === 'ok' ? 'health-dot' : 'health-dot degraded';
    healthBadge.innerHTML = `<span class="${dotClass}"></span> STT: ${escapeHtml(h.stt_provider)} · AI: ${escapeHtml(h.genai_provider)} (${escapeHtml(h.genai_model)})`;
  } catch (_) {
    healthBadge.innerHTML = `<span class="health-dot degraded"></span> Backend unreachable`;
  }
}

function render() {
  applyLangChrome();
  setActiveNav(state.view);
  if (state.view === 'detail') {
    mountCallDetailView(appEl, state.selectedCall, {
      backLabel: getLang() === 'ar' ? '→ العودة إلى السجل' : '← Back to Call History',
      onBack: () => {
        state.view = 'history';
        render();
      },
    });
  } else if (state.view === 'history') {
    mountCallHistoryView(appEl, {
      onSelectCall: call => {
        state.selectedCall = call;
        state.view = 'detail';
        render();
      },
    });
  } else {
    mountAnalyticsView(appEl);
  }
}

document.querySelectorAll('[data-view]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    state.view = el.dataset.view;
    render();
  });
});

langToggle.addEventListener('click', () => {
  const next = getLang() === 'en' ? 'ar' : 'en';
  localStorage.setItem('sage-lang', next);
  render();
});

refreshHealth();
render();
