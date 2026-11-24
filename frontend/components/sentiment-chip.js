export function renderChip(label, variant) {
  const cls = (variant || label || '').toLowerCase().replace(/\s+/g, '_');
  return `<span class="chip ${cls}">${label}</span>`;
}
