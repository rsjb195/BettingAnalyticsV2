import clsx from 'clsx';

/**
 * Compact data card for key metrics. Terminal-style with accent borders.
 *
 * @param {string} label - Metric label (e.g. "PPG")
 * @param {string|number} value - Primary value
 * @param {string} [subValue] - Secondary context line
 * @param {'cyan'|'green'|'amber'|'red'|'purple'} [accent] - Left border colour
 */
export default function StatCard({ label, value, subValue, accent = 'cyan' }) {
  const borderColour = {
    cyan: 'border-l-accent-cyan',
    green: 'border-l-accent-green',
    amber: 'border-l-accent-amber',
    red: 'border-l-accent-red',
    purple: 'border-l-accent-purple',
  }[accent];

  return (
    <div className={clsx('stat-card border-l-2', borderColour)}>
      <div className="text-[10px] font-data text-text-muted uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className="text-xl font-data font-bold text-text-primary tabular-nums">
        {value ?? '—'}
      </div>
      {subValue && (
        <div className="text-xs font-data text-text-secondary mt-0.5">
          {subValue}
        </div>
      )}
    </div>
  );
}
