export function renderScoreBar(label, score) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) {
    return `
      <div class="score-bar-wrap">
        <div class="score-bar-head">
          <span>${label}</span>
          <span style="color:var(--mu)">N/A</span>
        </div>
        <div class="score-bar-track">
          <div class="score-bar-fill" style="width:0%;background:var(--bd)"></div>
        </div>
      </div>
    `;
  }

  const num = Number(score);
  const pct = Math.max(0, Math.min(100, Math.round((num / 10) * 100)));
  let color = 'var(--score-low)';
  if (num >= 8) color = 'var(--score-high)';
  else if (num >= 5) color = 'var(--score-medium)';

  return `
    <div class="score-bar-wrap">
      <div class="score-bar-head">
        <span>${label}</span>
        <span>${num.toFixed(1)} / 10</span>
      </div>
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width:${pct}%;background:${color}"></div>
      </div>
    </div>
  `;
}
