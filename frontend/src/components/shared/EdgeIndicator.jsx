import clsx from 'clsx';
import { formatEdge } from '../../utils/formatters';
import { edgeClass } from '../../utils/colours';

/**
 * Edge percentage indicator with colour coding.
 *
 * @param {number|null} edge - Decimal edge (e.g. 0.05 = +5%)
 * @param {boolean} [showLabel] - Show "VALUE" / "MARGINAL" / "AVOID" label
 */
export default function EdgeIndicator({ edge, showLabel = false }) {
  const cls = edgeClass(edge);

  let label = null;
  if (showLabel && edge !== null && edge !== undefined) {
    if (edge > 0.05) label = 'VALUE';
    else if (edge > 0.01) label = 'MARGINAL';
    else if (edge <= 0) label = 'AVOID';
  }

  return (
    <div className="flex items-center gap-2">
      <span className={clsx('font-data text-sm tabular-nums', cls)}>
        {formatEdge(edge)}
      </span>
      {label && (
        <span className={clsx(
          'text-[9px] font-data font-bold px-1.5 py-0.5 uppercase tracking-wider',
          edge > 0.05 ? 'bg-accent-green/10 text-accent-green' :
          edge > 0.01 ? 'bg-accent-amber/10 text-accent-amber' :
          'bg-accent-red/10 text-accent-red',
        )}>
          {label}
        </span>
      )}
    </div>
  );
}
