import { escapeHtml } from '../components/escape.js';
import { renderScoreBar } from '../components/score-bar.js';
import { renderChip } from '../components/sentiment-chip.js';

function formatSec(sec) {
  const s = Math.max(0, Math.floor(Number(sec)));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}

function highlightEvidence(text, evidenceList) {
  let html = escapeHtml(text);
  const valid = (evidenceList || [])
    .map(e => String(e || '').trim())
    .filter(e => e.length >= 4)
    .sort((a, b) => b.length - a.length);

  for (const quote of valid) {
    const escapedQ = escapeHtml(quote);
    if (html.includes(escapedQ)) {
      html = html.split(escapedQ).join(`<mark class="ev-mark">${escapedQ}</mark>`);
    }
  }
  return html;
}

function csvCell(val) {
  return `"${String(val ?? '').replace(/"/g, '""')}"`;
}

export function mountCallDetailView(
  container,
  call,
  { onBack, backLabel = '← Close Report', audioPlayer = null } = {},
) {
  if (!call) {
    container.innerHTML = `<div class="card"><p>No call selected.</p></div>`;
    return;
  }

  const s = call.sentiment;
  const p = call.problem;
  const a = call.agent_evaluation;
  const r = call.resolution;
  const ops = call.operational_signals || {};
  const risk = call.risk_assessment || { score: 0, level: 'low', factors: [] };
  const meta = call.analysis_meta || {};

  const allEvidence = [
    ...(s.evidence || []),
    ...(a.evaluation_evidence || []),
    ...(p.root_cause_evidence || []),
    ...(ops.signal_evidence || []),
  ];

  const hasTimestamps = (call.speakers || []).some(
    t => t.start_seconds !== null && t.start_seconds !== undefined,
  );

  const speakersHtml = (call.speakers || []).length
    ? call.speakers.map(t => {
        const hasTs = t.start_seconds !== null && t.start_seconds !== undefined;
        const tsBtn = hasTs
          ? `<button type="button" class="ts-pill no-print" data-seek="${Number(t.start_seconds)}" title="Jump audio to ${formatSec(t.start_seconds)}">${formatSec(t.start_seconds)}</button>`
          : '';
        return `
          <div class="turn ${escapeHtml(t.speaker)}">
            <div class="turn-speaker">
              <span>${escapeHtml(t.speaker)} · Turn ${Number(t.turn_index)}</span>
              ${tsBtn}
            </div>
            <div dir="auto">${highlightEvidence(t.text, allEvidence)}</div>
          </div>
        `;
      }).join('')
    : call.raw_transcript
      ? `<div class="turn unknown"><div class="turn-speaker">Raw Transcript</div><div dir="auto">${highlightEvidence(call.raw_transcript, allEvidence)}</div></div>`
      : '<p style="color:var(--mu)">No speaker turns extracted.</p>';

  const lowConfBanner = (call.low_confidence_flags || []).length
    ? `<div class="alert alert-warn" style="margin-bottom:14px">
         Confidence Warnings: ${call.low_confidence_flags.map(f => `<code>${escapeHtml(f)}</code>`).join(', ')}
       </div>`
    : '';

  const consistencyBanner = (call.consistency_warnings || []).length
    ? `<div class="alert alert-info" style="margin-bottom:14px">
         Validation & Guardrail Notes:
         <ul class="evidence-list" style="margin-top:6px">${call.consistency_warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>
       </div>`
    : '';

  const emotionsHtml = (s.emotions || []).length
    ? `<div class="kw-list">${s.emotions.map(em => `<span class="kw-tag">${escapeHtml(em)}</span>`).join('')}</div>`
    : '';

  const keywordsHtml = (p.keywords || []).length
    ? `<div class="kw-list">${p.keywords.map(k => `<span class="kw-tag" dir="auto">${escapeHtml(k)}</span>`).join('')}</div>`
    : '';

  const painPointsHtml = (p.pain_points || []).length
    ? `<div style="margin-top:12px">
         <strong style="font-size:13px">Customer Pain Points</strong>
         <ul class="evidence-list">${p.pain_points.map(pt => `<li dir="auto">${escapeHtml(pt)}</li>`).join('')}</ul>
       </div>`
    : '';

  const rootCauseHtml = p.root_cause
    ? `<div style="margin-top:12px">
         <strong style="font-size:13px">Root Cause (Evidence-Supported)</strong>
         <p style="font-size:13px;margin-top:4px" dir="auto">${escapeHtml(p.root_cause)}</p>
         ${(p.root_cause_evidence || []).length ? `<ul class="evidence-list">${p.root_cause_evidence.map(e => `<li dir="auto">“${escapeHtml(e)}”</li>`).join('')}</ul>` : ''}
       </div>`
    : `<p style="font-size:12px;color:var(--mu);margin-top:10px">Root cause: Insufficient explicit evidence in transcript.</p>`;

  const agentApplicable = a.applicable !== false && a.overall_score !== null && a.overall_score !== undefined;
  const agentOverallDisplay = agentApplicable ? `${Number(a.overall_score).toFixed(1)} / 10` : 'N/A (No agent speech)';

  const signalBadges = [
    ops.repeated_complaint ? renderChip('Repeated Complaint', 'high') : '',
    ops.missed_commitment ? renderChip('Missed Commitment', 'high') : '',
    ops.potential_sla_violation ? renderChip('Potential SLA Violation', 'critical') : '',
    r.escalation_required ? renderChip('Escalation Required', 'critical') : '',
  ].filter(Boolean).join('');

  const followUpHtml = (r.follow_up_actions || []).length
    ? `<ul class="evidence-list">${r.follow_up_actions.map(act => `<li dir="auto">${escapeHtml(act)}</li>`).join('')}</ul>`
    : '';

  const evalEvidenceHtml = (a.evaluation_evidence || []).length
    ? `<div style="margin-top:14px">
         <strong style="font-size:13px">Agent Evidence Quotes</strong>
         <ul class="evidence-list">${a.evaluation_evidence.map(ev => `<li dir="auto">“${escapeHtml(ev)}”</li>`).join('')}</ul>
       </div>`
    : '';

  const modelBadge = meta.provider
    ? ` · Engine: ${escapeHtml(meta.provider)} (${escapeHtml(meta.model || '')})${meta.cache_hit ? ' [cached]' : meta.latency_ms ? ` · ${(meta.latency_ms / 1000).toFixed(1)}s` : ''}`
    : '';

  container.innerHTML = `
    <div class="card card-muted" style="margin-bottom:28px">
      <div class="report-header">
        <div>
          ${onBack ? `<button id="backBtn" class="btn btn-secondary btn-sm no-print" style="margin-bottom:10px">${escapeHtml(backLabel)}</button>` : ''}
          <h2 style="margin:0">${escapeHtml(call.call_id)}</h2>
          <p style="color:var(--mu);font-size:13px;margin-top:4px">
            Analyzed: ${escapeHtml(new Date(call.analyzed_at).toLocaleString())} · Source: ${escapeHtml(call.source || 'text')} · Language: ${escapeHtml(call.transcript_language.toUpperCase())} · Confidence: ${Math.round(call.confidence_score * 100)}%${modelBadge}
          </p>
        </div>
        <div class="no-print" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          ${renderChip(escapeHtml(p.category.replace(/_/g, ' ')), 'neutral')}
          ${renderChip(escapeHtml(p.priority), escapeHtml(p.priority))}
          <button id="exportJsonBtn" class="btn btn-secondary btn-sm">Export JSON</button>
          <button id="exportSingleCsvBtn" class="btn btn-secondary btn-sm">Export CSV</button>
          <button id="exportPdfBtn" class="btn btn-secondary btn-sm">Export PDF</button>
        </div>
      </div>

      ${lowConfBanner}
      ${consistencyBanner}

      <div class="report-grid-2">
        <div class="card">
          <h3 class="section-title">Customer Sentiment & Emotions</h3>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            ${renderChip(escapeHtml(s.overall), escapeHtml(s.overall))}
            <strong style="font-size:22px">${Number(s.score).toFixed(1)} / 10</strong>
          </div>
          <p style="font-size:13px;color:var(--mu)">Trajectory: <strong>${escapeHtml(s.trajectory)}</strong></p>
          ${emotionsHtml}
          <ul class="evidence-list">${(s.evidence || []).map(e => `<li dir="auto">“${escapeHtml(e)}”</li>`).join('')}</ul>
        </div>

        <div class="card">
          <h3 class="section-title">Rule-Based Customer Risk Score</h3>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            ${renderChip(`${escapeHtml(risk.level)} risk`, escapeHtml(risk.level))}
            <strong style="font-size:22px">${Number(risk.score)} / 100</strong>
          </div>
          <p style="font-size:11px;color:var(--mu);margin-bottom:8px">Deterministic rule-based risk score (not a predicted churn probability).</p>
          <ul class="evidence-list">${(risk.factors || []).map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul>
        </div>
      </div>

      <div class="report-grid-2">
        <div class="card">
          <h3 class="section-title">Issue Resolution & Escalation</h3>
          <div style="margin-bottom:10px">
            ${renderChip(r.resolved ? 'Resolved' : 'Unresolved', r.resolved ? 'positive' : 'negative')}
            <span style="margin-inline-start:8px;font-size:13px;color:var(--mu)">${escapeHtml(r.resolution_type.replace(/_/g, ' '))}</span>
          </div>
          <p style="font-size:14px;margin-bottom:8px" dir="auto">${escapeHtml(r.resolution_summary || 'No resolution summary provided.')}</p>
          <p style="font-size:13px;color:var(--mu)">
            Follow-up required: <strong>${r.follow_up_required ? 'Yes' : 'No'}</strong> ·
            Escalation required: <strong>${r.escalation_required ? 'Yes' : 'No'}</strong>
          </p>
          ${r.escalation_reason ? `<p style="font-size:13px;color:var(--danger);margin-top:6px" dir="auto">Escalation reason: ${escapeHtml(r.escalation_reason)}</p>` : ''}
          ${followUpHtml}
        </div>

        <div class="card">
          <h3 class="section-title">Operational Risk Signals</h3>
          <div class="signal-grid">${signalBadges || '<span style="font-size:13px;color:var(--mu)">No SLA violations, missed commitments, or repeat-complaint flags triggered.</span>'}</div>
          ${(ops.signal_evidence || []).length ? `<ul class="evidence-list">${ops.signal_evidence.map(e => `<li dir="auto">“${escapeHtml(e)}”</li>`).join('')}</ul>` : ''}
        </div>
      </div>

      <div class="card" style="margin-bottom:20px">
        <h3 class="section-title">Problem, Pain Points & Root Cause</h3>
        <p style="font-size:15px;font-weight:600;margin-bottom:6px" dir="auto">${escapeHtml(p.summary)}</p>
        <p style="font-size:13px;color:var(--mu)" dir="auto">Priority rationale: ${escapeHtml(p.priority_rationale)}</p>
        ${keywordsHtml}
        ${painPointsHtml}
        ${rootCauseHtml}
      </div>

      <div class="card" style="margin-bottom:20px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <h3 class="section-title" style="margin:0">Agent Performance Evaluation</h3>
          <strong>Overall: ${agentOverallDisplay}</strong>
        </div>
        <div class="report-grid-2">
          ${renderScoreBar('Empathy', a.empathy_score)}
          ${renderScoreBar('Clarity', a.clarity_score)}
          ${renderScoreBar('Resolution Effectiveness', a.resolution_effectiveness_score)}
          ${renderScoreBar('Professionalism', a.professionalism_score)}
        </div>
        <div class="report-grid-2" style="margin-top:16px;margin-bottom:0">
          <div>
            <strong style="font-size:13px">Strengths</strong>
            <ul class="evidence-list">${(a.strengths || []).length ? a.strengths.map(x => `<li dir="auto">${escapeHtml(x)}</li>`).join('') : `<li style="color:var(--mu)">${agentApplicable ? 'None noted' : 'N/A'}</li>`}</ul>
          </div>
          <div>
            <strong style="font-size:13px">Areas for Improvement</strong>
            <ul class="evidence-list">${(a.areas_for_improvement || []).map(x => `<li dir="auto">${escapeHtml(x)}</li>`).join('')}</ul>
          </div>
        </div>
        ${evalEvidenceHtml}
      </div>

      <div class="report-grid-2">
        <div class="card">
          <h3 class="section-title">Call Summary & Insights</h3>
          <p style="font-size:14px;line-height:1.6;margin-bottom:12px" dir="auto">${escapeHtml(call.call_summary)}</p>
          <strong style="font-size:13px">Actionable Insights</strong>
          <ul class="evidence-list">${(call.key_insights || []).map(x => `<li dir="auto">${escapeHtml(x)}</li>`).join('')}</ul>
        </div>
        <div class="card">
          <h3 class="section-title">Recommendations</h3>
          <ul class="evidence-list" style="margin-top:0">${(call.recommendations || []).map(x => `<li dir="auto">${escapeHtml(x)}</li>`).join('')}</ul>
        </div>
      </div>

      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px">
          <h3 class="section-title" style="margin:0">Transcript & Evidence Highlights</h3>
          <span style="font-size:12px;color:var(--mu)">
            ${hasTimestamps ? 'Click any timestamp to jump audio playback' : 'Acoustic timestamps not provided by STT model'} · Highlighted phrases = grounded evidence
          </span>
        </div>
        ${speakersHtml}
      </div>
    </div>
  `;

  if (onBack && container.querySelector('#backBtn')) {
    container.querySelector('#backBtn').addEventListener('click', onBack);
  }
  container.querySelectorAll('.ts-pill[data-seek]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (audioPlayer && audioPlayer.src) {
        audioPlayer.currentTime = Number(btn.dataset.seek);
        audioPlayer.play().catch(() => {});
      }
    });
  });
  container.querySelector('#exportJsonBtn').addEventListener('click', () => {
    const aEl = document.createElement('a');
    aEl.href = URL.createObjectURL(new Blob([JSON.stringify(call, null, 2)], { type: 'application/json' }));
    aEl.download = `${call.call_id}.json`;
    aEl.click();
  });
  container.querySelector('#exportSingleCsvBtn').addEventListener('click', () => {
    const rows = [
      ['call_id', 'analyzed_at', 'category', 'priority', 'sentiment', 'satisfaction_score', 'risk_score', 'risk_level', 'agent_score', 'resolved', 'sla_violation', 'root_cause', 'summary'],
      [
        call.call_id, call.analyzed_at, p.category, p.priority, s.overall, s.score,
        risk.score, risk.level, agentApplicable ? a.overall_score : 'N/A',
        r.resolved, ops.potential_sla_violation || false, p.root_cause || 'N/A', p.summary,
      ],
    ];
    const csv = '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\n');
    const aEl = document.createElement('a');
    aEl.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    aEl.download = `${call.call_id}.csv`;
    aEl.click();
  });
  container.querySelector('#exportPdfBtn').addEventListener('click', () => {
    window.print();
  });
}
