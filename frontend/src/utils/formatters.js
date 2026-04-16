/**
 * Formatting utilities for the trading terminal UI.
 */

/**
 * Format a decimal probability as a percentage string.
 * @param {number|null} prob - e.g. 0.453
 * @param {number} decimals
 * @returns {string} e.g. "45.3%"
 */
export function formatPct(prob, decimals = 1) {
  if (prob === null || prob === undefined) return '—';
  return `${(prob * 100).toFixed(decimals)}%`;
}

/**
 * Format decimal odds to 2dp.
 */
export function formatOdds(odds) {
  if (odds === null || odds === undefined || odds === 0) return '—';
  return odds.toFixed(2);
}

/**
 * Format currency value.
 */
export function formatCurrency(amount, currency = '$') {
  if (amount === null || amount === undefined) return '—';
  return `${currency}${amount.toFixed(2)}`;
}

/**
 * Format edge percentage (input is decimal, e.g. 0.05 = 5%).
 */
export function formatEdge(edge) {
  if (edge === null || edge === undefined) return '—';
  const pct = (edge * 100).toFixed(1);
  return edge > 0 ? `+${pct}%` : `${pct}%`;
}

/**
 * Format a date string to DD MMM YYYY.
 */
export function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Format a date as relative time (e.g. "2h ago", "Yesterday").
 */
export function formatRelativeTime(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now - d;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateStr);
}

/**
 * Format a form string with result letters.
 * @param {string} form - e.g. "WWDLW"
 * @returns {Array<{letter: string, colour: string}>}
 */
export function parseForm(form) {
  if (!form) return [];
  return form.split('').map((ch) => ({
    letter: ch,
    colour:
      ch === 'W' ? 'text-accent-green' :
      ch === 'D' ? 'text-accent-amber' :
      ch === 'L' ? 'text-accent-red' :
      'text-text-muted',
  }));
}

/**
 * Format a large number with commas.
 */
export function formatNumber(n) {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString('en-GB');
}
