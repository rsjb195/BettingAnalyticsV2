import OddsBadge from '../shared/OddsBadge';
import EdgeIndicator from '../shared/EdgeIndicator';

/**
 * Compact fixture card for dashboard/slate display.
 */
export default function FixtureCard({ fixture, onSelectOutcome, selectedLeg }) {
  const model = fixture.model || {};

  return (
    <div className="stat-card-accent p-3 space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm font-ui font-semibold text-text-primary">
          {fixture.home_team?.name || '?'} vs {fixture.away_team?.name || '?'}
        </span>
        <EdgeIndicator
          edge={Math.max(model.home_edge || 0, model.draw_edge || 0, model.away_edge || 0)}
          showLabel
        />
      </div>
      <div className="flex gap-3">
        {['home', 'draw', 'away'].map((outcome) => {
          const odds = fixture.odds?.[outcome];
          const edge = model[`${outcome}_edge`];
          return (
            <OddsBadge
              key={outcome}
              odds={odds}
              edge={edge}
              selected={selectedLeg?.selection === outcome}
              onClick={() => onSelectOutcome?.(fixture, outcome)}
            />
          );
        })}
      </div>
    </div>
  );
}
