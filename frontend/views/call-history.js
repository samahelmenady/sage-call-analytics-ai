import { escapeHtml } from '../components/escape.js';
import { t } from '../components/i18n.js';
import { renderChip } from '../components/sentiment-chip.js';

function csvCell(val) {
  return `"${String(val ?? '').replace(/"/g, '""')}"`;
}

export async function mountCallHistoryView(container, { onSelectCall }) {
  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:12px">
      <h1 style="margin:0">${escapeHtml(t('historyTitle'))}</h1>
      <button id="exportCsvBtn" class="btn btn-secondary btn-sm">${escapeHtml(t('exportCsv'))}</button>
    </div>
    <div class="filters-bar">
      <input id="filterSearch" class="input" style="max-width:240px" placeholder="${escapeHtml(t('searchPh'))}" />
      <select id="filterSentiment" class="select" style="max-width:155px">
        <option value="">All Sentiments</option>
        <option value="positive">Positive</option>
        <option value="neutral">Neutral</option>
        <option value="negative">Negative</option>
        <option value="mixed">Mixed</option>
      </select>
      <select id="filterCategory" class="select" style="max-width:155px">
        <option value="">All Categories</option>
        <option value="billing">Billing</option>
        <option value="technical">Technical</option>
        <option value="shipping">Shipping</option>
        <option value="account">Account</option>
        <option value="product_quality">Product Quality</option>
        <option value="returns">Returns</option>
        <option value="general_inquiry">General Inquiry</option>
        <option value="other">Other</option>
      </select>
      <select id="filterPriority" class="select" style="max-width:145px">
        <option value="">All Priorities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <select id="filterRisk" class="select" style="max-width:145px">
        <option value="">All Risk Levels</option>
        <option value="critical">Critical Risk</option>
        <option value="high">High Risk</option>
        <option value="medium">Medium Risk</option>
        <option value="low">Low Risk</option>
      </select>
      <select id="filterResolved" class="select" style="max-width:145px">
        <option value="">All Statuses</option>
        <option value="true">Resolved</option>
        <option value="false">Unresolved</option>
      </select>
      <select id="filterSort" class="select" style="max-width:165px">
        <option value="date_desc">Newest First</option>
        <option value="date_asc">Oldest First</option>
        <option value="risk_desc">Highest Risk</option>
        <option value="sentiment_asc">Lowest Satisfaction</option>
        <option value="agent_desc">Highest Agent Score</option>
      </select>
    </div>
    <div class="card table-wrap">
      <table>
        <thead>
          <tr>
            <th>Call ID</th>
            <th>Date</th>
            <th>Category</th>
            <th>Priority</th>
            <th>Sentiment</th>
            <th>Risk Score</th>
            <th>Agent Score</th>
            <th>Resolved</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="callsTbody"><tr><td colspan="9">Loading...</td></tr></tbody>
      </table>
    </div>
  `;

  let currentCalls = [];
  let timer = null;

  async function loadCalls() {
    const params = new URLSearchParams({ limit: '100' });
    const q = container.querySelector('#filterSearch').value.trim();
    const sent = container.querySelector('#filterSentiment').value;
    const cat = container.querySelector('#filterCategory').value;
    const prio = container.querySelector('#filterPriority').value;
    const risk = container.querySelector('#filterRisk').value;
    const resv = container.querySelector('#filterResolved').value;
    const sortBy = container.querySelector('#filterSort').value;

    if (q) params.set('search', q);
    if (sent) params.set('sentiment', sent);
    if (cat) params.set('category', cat);
    if (prio) params.set('priority', prio);
    if (risk) params.set('risk_level', risk);
    if (resv) params.set('resolved', resv);
    if (sortBy) params.set('sort_by', sortBy);

    const tbody = container.querySelector('#callsTbody');
    try {
      const resp = await fetch(`/api/calls?${params.toString()}`);
      currentCalls = await resp.json();
      if (!resp.ok) throw new Error(currentCalls.detail || 'Failed to load calls');
      if (!currentCalls.length) {
        tbody.innerHTML = `<tr><td colspan="9" style="color:var(--mu)">No matching calls found.</td></tr>`;
        return;
      }
      tbody.innerHTML = currentCalls.map(c => {
        const ag = c.agent_evaluation;
        const agentTxt = (ag.applicable !== false && ag.overall_score !== null && ag.overall_score !== undefined)
          ? `${Number(ag.overall_score).toFixed(1)} / 10`
          : t('na');
        const rk = c.risk_assessment || { score: 0, level: 'low' };
        return `
          <tr data-id="${escapeHtml(c.call_id)}">
            <td><strong>${escapeHtml(c.call_id)}</strong></td>
            <td>${escapeHtml(new Date(c.analyzed_at).toLocaleDateString())}</td>
            <td>${escapeHtml(c.problem.category.replace(/_/g, ' '))}</td>
            <td>${renderChip(escapeHtml(c.problem.priority), escapeHtml(c.problem.priority))}</td>
            <td>${renderChip(escapeHtml(c.sentiment.overall), escapeHtml(c.sentiment.overall))} (${Number(c.sentiment.score).toFixed(1)})</td>
            <td>${renderChip(`${Number(rk.score)} (${escapeHtml(rk.level)})`, escapeHtml(rk.level))}</td>
            <td>${agentTxt}</td>
            <td>${c.resolution.resolved ? '✓' : '✗'}</td>
            <td><button class="btn btn-secondary btn-sm delete-row-btn" data-delete-id="${escapeHtml(c.call_id)}">Delete</button></td>
          </tr>
        `;
      }).join('');

      tbody.querySelectorAll('tr[data-id]').forEach(row => {
        row.addEventListener('click', () => {
          const found = currentCalls.find(x => x.call_id === row.dataset.id);
          if (found) onSelectCall(found);
        });
      });

      tbody.querySelectorAll('.delete-row-btn').forEach(btn => {
        btn.addEventListener('click', async e => {
          e.stopPropagation();
          btn.disabled = true;
          await fetch(`/api/calls/${encodeURIComponent(btn.dataset.deleteId)}`, { method: 'DELETE' });
          await loadCalls();
        });
      });
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="9" style="color:var(--danger)">Error: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  container.querySelector('#filterSearch').addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(loadCalls, 220);
  });
  ['#filterSentiment', '#filterCategory', '#filterPriority', '#filterRisk', '#filterResolved', '#filterSort'].forEach(sel => {
    container.querySelector(sel).addEventListener('change', loadCalls);
  });

  container.querySelector('#exportCsvBtn').addEventListener('click', () => {
    if (!currentCalls.length) return;
    const rows = [
      ['call_id', 'analyzed_at', 'category', 'priority', 'sentiment', 'satisfaction_score', 'risk_score', 'risk_level', 'agent_score', 'resolved', 'sla_violation', 'root_cause', 'summary'],
      ...currentCalls.map(c => {
        const ag = c.agent_evaluation;
        const rk = c.risk_assessment || { score: 0, level: 'low' };
        const ops = c.operational_signals || {};
        return [
          c.call_id, c.analyzed_at, c.problem.category, c.problem.priority,
          c.sentiment.overall, c.sentiment.score, rk.score, rk.level,
          (ag.applicable !== false && ag.overall_score !== null && ag.overall_score !== undefined) ? ag.overall_score : 'N/A',
          c.resolution.resolved, ops.potential_sla_violation || false,
          c.problem.root_cause || 'N/A', c.problem.summary,
        ];
      }),
    ];
    const csv = '\uFEFF' + rows.map(r => r.map(csvCell).join(',')).join('\n');
    const aEl = document.createElement('a');
    aEl.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    aEl.download = 'sage-calls.csv';
    aEl.click();
  });

  await loadCalls();
}
