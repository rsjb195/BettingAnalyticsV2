/**
 * Design token colours for the trading terminal UI.
 * Used by Recharts, inline styles, and dynamic class generation.
 */

export const COLOURS = {
  bg: '#0a0a0f',
  bgSecondary: '#0d1117',
  card: '#111827',
  elevated: '#1a2332',
  border: '#1e2d3d',
  borderAccent: 'rgba(0, 212, 255, 0.13)',

  cyan: '#00d4ff',
  green: '#00ff88',
  amber: '#ffaa00',
  red: '#ff4444',
  purple: '#a855f7',

  textPrimary: '#e2e8f0',
  textSecondary: '#94a3b8',
  textMuted: '#475569',
};

/**
 * Return the appropriate colour for an edge percentage.
 * @param {number|null} edge - Edge percentage (e.g. 0.05 = 5%)
 * @returns {string} Hex colour
 */
export function edgeColour(edge) {
  if (edge === null || edge === undefined) return COLOURS.textMuted;
  if (edge > 0.05) return COLOURS.green;
  if (edge > 0.01) return COLOURS.amber;
  if (edge > 0) return COLOURS.textSecondary;
  return COLOURS.red;
}

/**
 * Return the CSS class for an edge percentage.
 */
export function edgeClass(edge) {
  if (edge === null || edge === undefined) return 'edge-neutral';
  if (edge > 0.05) return 'edge-positive';
  if (edge > 0.01) return 'edge-marginal';
  if (edge > 0) return 'edge-neutral';
  return 'edge-negative';
}

/**
 * Colour for match result type (used in ticker and form displays).
 */
export function resultColour(result) {
  switch (result) {
    case 'W':
    case 'home_win':
      return COLOURS.cyan;
    case 'L':
    case 'away_win':
      return COLOURS.amber;
    case 'D':
    case 'draw':
      return COLOURS.textPrimary;
    default:
      return COLOURS.textMuted;
  }
}

/** Recharts-compatible colour array for multi-series charts. */
export const CHART_COLOURS = [
  COLOURS.cyan,
  COLOURS.green,
  COLOURS.amber,
  COLOURS.purple,
  COLOURS.red,
];
