import { escapeHtml } from '../components/escape.js';
import { t } from '../components/i18n.js';
import { renderChip } from '../components/sentiment-chip.js';
import { mountUploadView } from './upload.js';

export async function mountAnalyticsView(container) {
  container.innerHTML = `
    <div id="dashUploadSection" style="margin-bottom:28px"></div>
    <hr style="border:0;border-top:1px solid var(--bd);margin:0 0 28px" />
    <div id="dashKpiSection"><p style="color:var(--mu)">Loading dashboard metrics...</p></div>
  `;

  const uploadSection = container.querySelector('#dashUploadSection');
  const kpiSection = container.querySelector('#dashKpiSection');
  const charts = [];

  function destroyCharts() {
    while (charts.length) {
      const ch = charts.pop();
      try { ch.destroy(); } catch (_) {}
    }
  }

  let uploadHandle = null;
  let searchTimer = null;

  async function refreshRecentCallsTable() {
    const tbody = kpiSection.querySelector('#recentCallsBody');
    if (!tbody) return;
    const params = new URLSearchParams({ limit: '15' });
    const q = kpiSection.querySelector('#dashSearch')?.value.trim();
    const sent = kpiSection.querySelector('#dashSentFilter')?.value;
    const risk = kpiSection.querySelector('#dashRiskFilter')?.value;
    if (q) params.set('search', q);
    if (sent) params.set('sentiment', sent);
    if (risk) params.set('risk_level', risk);

    const callsResp = await fetch(`/api/calls?${params.toString()}`);
    const recentCalls = await callsResp.json();
    if (!callsResp.ok) return;

    tbody.innerHTML = recentCalls.length
      ? recentCalls.map(c => {
          const ag = c.agent_evaluation;
          const agentTxt = (ag.applicable !== false && ag.overall_score !== null && ag.overall_score !== undefined)
            ? `${Number(ag.overall_score).toFixed(1)} / 10`
            : t('na');
          const risk = c.risk_assessment || { score: 0, level: 'low' };
          return `
            <tr data-call-id="${escapeHtml(c.call_id)}">
              <td><strong>${escapeHtml(c.call_id)}</strong></td>
              <td>${escapeHtml(new Date(c.analyzed_at).toLocaleDateString())}</td>
              <td>${escapeHtml(c.problem.category.replace(/_/g, ' '))}</td>
              <td>${renderChip(escapeHtml(c.problem.priority), escapeHtml(c.problem.priority))}</td>
              <td>${renderChip(escapeHtml(c.sentiment.overall), escapeHtml(c.sentiment.overall))} (${Number(c.sentiment.score).toFixed(1)})</td>
              <td>${renderChip(`${Number(risk.score)} (${escapeHtml(risk.level)})`, escapeHtml(risk.level))}</td>
              <td>${agentTxt}</td>
              <td>${c.resolution.resolved ? '✓' : '✗'}</td>
              <td><button class="btn btn-secondary btn-sm delete-call-btn" data-delete-id="${escapeHtml(c.call_id)}">Delete</button></td>
            </tr>
          `;
        }).join('')
      : `<tr><td colspan="9" style="color:var(--mu)">No analyzed calls found.</td></tr>`;

    tbody.querySelectorAll('tr[data-call-id]').forEach(row => {
      row.addEventListener('click', () => {
        const found = recentCalls.find(c => c.call_id === row.dataset.callId);
        if (found && uploadHandle) uploadHandle.showCall(found);
      });
    });

    tbody.querySelectorAll('.delete-call-btn').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        btn.disabled = true;
        await fetch(`/api/calls/${encodeURIComponent(btn.dataset.deleteId)}`, { method: 'DELETE' });
        await loadDashboardStats();
      });
    });
  }

  async function loadDashboardStats() {
    try {
      const anaResp = await fetch('/api/analytics');
      const data = await anaResp.json();
      if (!anaResp.ok) throw new Error(data.detail || 'Failed to load analytics');

      destroyCharts();

      const ag = data.avg_agent_scores || {};
      const avgAgentDisplay = (ag.overall !== null && ag.overall !== undefined)
        ? `${Number(ag.overall).toFixed(1)} <span style="font-size:15px;color:var(--mu)">/ 10</span>`
        : `<span style="color:var(--mu)">${escapeHtml(t('na'))}</span>`;

      kpiSection.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px">
          <h2 style="margin:0">${escapeHtml(t('dashTitle'))}</h2>
          ${data.top_issues && data.top_issues.length
            ? `<div style="font-size:13px;color:var(--mu)">Top issues: ${data.top_issues.map(i => `<span class="kw-tag">${escapeHtml(i.replace(/_/g, ' '))}</span>`).join(' ')}</div>`
            : ''}
        </div>

        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">${escapeHtml(t('kpiCalls'))}</div>
            <div class="kpi-value">${Number(data.total_calls)}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">${escapeHtml(t('kpiSat'))}</div>
            <div class="kpi-value">${Number(data.avg_satisfaction_score).toFixed(1)} <span style="font-size:15px;color:var(--mu)">/ 10</span></div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">${escapeHtml(t('kpiRes'))}</div>
            <div class="kpi-value">${Math.round(Number(data.resolution_rate) * 100)}%</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">${escapeHtml(t('kpiAgent'))} (${Number(data.evaluated_agent_calls || 0)} eval)</div>
            <div class="kpi-value">${avgAgentDisplay}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">${escapeHtml(t('kpiRisk'))}</div>
            <div class="kpi-value">${Number(data.avg_risk_score || 0).toFixed(1)} <span style="font-size:15px;color:var(--mu)">/ 100</span></div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">${escapeHtml(t('kpiAlerts'))}</div>
            <div class="kpi-value">${Number(data.high_risk_calls || 0)} <span style="font-size:14px;color:var(--mu)">/ ${Number(data.sla_violation_count || 0)} SLA</span></div>
          </div>
        </div>

        <div class="charts-grid">
          <div class="card">
            <h3 class="section-title">${escapeHtml(t('chartSent'))}</h3>
            <div class="chart-box"><canvas id="sentimentChart"></canvas></div>
          </div>
          <div class="card">
            <h3 class="section-title">${escapeHtml(t('chartCat'))}</h3>
            <div class="chart-box"><canvas id="categoryChart"></canvas></div>
          </div>
          <div class="card">
            <h3 class="section-title">${escapeHtml(t('chartPrio'))}</h3>
            <div class="chart-box"><canvas id="priorityChart"></canvas></div>
          </div>
          <div class="card">
            <h3 class="section-title">${escapeHtml(t('chartAgent'))}</h3>
            <div class="chart-box"><canvas id="agentChart"></canvas></div>
          </div>
        </div>

        <div class="card" style="margin-bottom:24px">
          <h3 class="section-title">${escapeHtml(t('chartTrend'))}</h3>
          <div class="chart-box" style="height:200px"><canvas id="trendChart"></canvas></div>
        </div>

        <div class="card table-wrap">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px">
            <h3 class="section-title" style="margin:0">${escapeHtml(t('recentCalls'))}</h3>
            <div class="filters-bar" style="margin:0">
              <input id="dashSearch" class="input" style="min-width:220px;width:auto" placeholder="${escapeHtml(t('searchPh'))}" />
              <select id="dashSentFilter" class="select" style="width:auto">
                <option value="">All Sentiments</option>
                <option value="positive">Positive</option>
                <option value="neutral">Neutral</option>
                <option value="negative">Negative</option>
                <option value="mixed">Mixed</option>
              </select>
              <select id="dashRiskFilter" class="select" style="width:auto">
                <option value="">All Risk Levels</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
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
            <tbody id="recentCallsBody"><tr><td colspan="9">Loading...</td></tr></tbody>
          </table>
        </div>
      `;

      if (window.Chart) {
        const s = data.sentiment_distribution;
        charts.push(new window.Chart(kpiSection.querySelector('#sentimentChart'), {
          type: 'doughnut',
          data: {
            labels: ['Positive', 'Neutral', 'Negative', 'Mixed'],
            datasets: [{
              data: [s.positive, s.neutral, s.negative, s.mixed],
              backgroundColor: ['#2F5D46', '#1A5276', '#A4452B', '#D68910'],
            }],
          },
          options: { responsive: true, maintainAspectRatio: false },
        }));

        const cats = Object.keys(data.category_breakdown || {});
        const catVals = Object.values(data.category_breakdown || {});
        charts.push(new window.Chart(kpiSection.querySelector('#categoryChart'), {
          type: 'bar',
          data: {
            labels: cats.length ? cats.map(c => c.replace(/_/g, ' ')) : ['No Data'],
            datasets: [{
              label: 'Calls',
              data: catVals.length ? catVals : [0],
              backgroundColor: '#1A1816',
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
          },
        }));

        const rdist = data.risk_distribution || {};
        charts.push(new window.Chart(kpiSection.querySelector('#priorityChart'), {
          type: 'doughnut',
          data: {
            labels: ['Critical Risk', 'High Risk', 'Medium Risk', 'Low Risk'],
            datasets: [{
              data: [rdist.critical || 0, rdist.high || 0, rdist.medium || 0, rdist.low || 0],
              backgroundColor: ['#A4452B', '#D68910', '#2471A3', '#2F5D46'],
            }],
          },
          options: { responsive: true, maintainAspectRatio: false },
        }));

        const hasAgentEvals = Number(data.evaluated_agent_calls || 0) > 0;
        charts.push(new window.Chart(kpiSection.querySelector('#agentChart'), {
          type: 'bar',
          data: {
            labels: ['Empathy', 'Clarity', 'Resolution', 'Professionalism'],
            datasets: [{
              label: hasAgentEvals ? 'Avg Score (/10)' : 'No Agent Evals (N/A)',
              data: hasAgentEvals
                ? [ag.empathy || 0, ag.clarity || 0, ag.resolution_effectiveness || 0, ag.professionalism || 0]
                : [0, 0, 0, 0],
              backgroundColor: '#2F5D46',
            }],
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { min: 0, max: 10 } },
          },
        }));

        const trends = data.daily_trends || [];
        charts.push(new window.Chart(kpiSection.querySelector('#trendChart'), {
          type: 'line',
          data: {
            labels: trends.length ? trends.map(tr => tr.date) : ['No Data'],
            datasets: [
              {
                label: 'Avg Satisfaction (0-10)',
                data: trends.length ? trends.map(tr => tr.avg_satisfaction) : [0],
                borderColor: '#2F5D46',
                backgroundColor: 'rgba(47,93,70,0.1)',
                tension: 0.25,
                yAxisID: 'ySat',
              },
              {
                label: 'Avg Risk Score (0-100)',
                data: trends.length ? trends.map(tr => tr.avg_risk_score) : [0],
                borderColor: '#A4452B',
                backgroundColor: 'rgba(164,69,43,0.1)',
                tension: 0.25,
                yAxisID: 'yRisk',
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              ySat: { type: 'linear', position: 'left', min: 0, max: 10 },
              yRisk: { type: 'linear', position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false } },
            },
          },
        }));
      }

      kpiSection.querySelector('#dashSearch').addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(refreshRecentCallsTable, 220);
      });
      kpiSection.querySelector('#dashSentFilter').addEventListener('change', refreshRecentCallsTable);
      kpiSection.querySelector('#dashRiskFilter').addEventListener('change', refreshRecentCallsTable);

      await refreshRecentCallsTable();
    } catch (err) {
      kpiSection.innerHTML = `<div class="alert alert-error">Error loading dashboard: ${escapeHtml(err.message)}</div>`;
    }
  }

  uploadHandle = mountUploadView(uploadSection, {
    onAnalysisComplete: () => loadDashboardStats(),
  });
  await loadDashboardStats();
}
