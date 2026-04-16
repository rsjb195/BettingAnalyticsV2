import clsx from 'clsx';
import { formatOdds } from '../../utils/formatters';

/**
 * Compact odds display badge with colour-coded edge indicator.
 *
 * @param {number} odds - Decimal odds
 * @param {number} [edge] - Our edge vs market (decimal, e.g. 0.05)
 * @param {boolean} [selected] - Whether this outcome is selected for an accumulator
 * @param {Function} [onClick]
 */
export default function OddsBadge({ odds, edge, selected, onClick }) {
  const edgeBg =
    edge > 0.05 ? 'bg-accent-green/10 border-accent-green/40' :
    edge > 0.01 ? 'bg-accent-amber/10 border-accent-amber/40' :
    edge > 0 ? 'bg-terminal-elevated border-terminal-border' :
    'bg-accent-red/5 border-accent-red/20';

  const edgeText =
    edge > 0.05 ? 'text-accent-green' :
    edge > 0.01 ? 'text-accent-amber' :
    edge > 0 ? 'text-text-secondary' :
    'text-accent-red';

  return (
    <button
      onClick={onClick}
      className={clsx(
        'px-3 py-1.5 border font-data text-sm tabular-nums transition-all',
        selected ? 'bg-accent-cyan/20 border-accent-cyan text-accent-cyan glow-cyan' : edgeBg,
        !selected && edgeText,
        onClick && 'cursor-pointer hover:brightness-125',
      )}
    >
      {formatOdds(odds)}
    </button>
  );
}
