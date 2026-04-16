import OddsBadge from '../shared/OddsBadge';
import EdgeIndicator from '../shared/EdgeIndicator';
import { formatPct, parseForm } from '../../utils/formatters';

export default function FixtureRow({ fixture, onSelectOutcome, selectedLeg }) {
  const model = fixture.model || {};
  const bestEdge = Math.max(model.home_edge || 0, model.draw_edge || 0, model.away_edge || 0);

  return (
    <div className="stat-card-accent p-3 space-y-2">
      <div className="flex justify-between items-center">
        <div>
          <span className="text-sm font-ui font-semibold text-text-primary">{fixture.home_team?.name}</span>
          <span className="text-text-muted mx-2">vs</span>
          <span className="text-sm font-ui font-semibold text-text-primary">{fixture.away_team?.name}</span>
        </div>
        <EdgeIndicator edge={bestEdge} showLabel />
      </div>
      <div className="flex gap-4">
        {['home', 'draw', 'away'].map((outcome) => (
          <div key={outcome} className="flex-1">
            <div className="text-[10px] font-data text-text-muted mb-1">{outcome.toUpperCase()}</div>
            <OddsBadge
              odds={fixture.odds?.[outcome]}
              edge={model[`${outcome}_edge`]}
              selected={selectedLeg?.selection === outcome}
              onClick={() => onSelectOutcome?.(fixture, outcome)}
            />
            <div className="text-[10px] font-data text-text-muted mt-1">
              {model[`our_${outcome}_prob`] ? formatPct(model[`our_${outcome}_prob`]) : '—'}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-4 text-[10px] font-data text-text-muted">
        {fixture.referee && <span>REF: {fixture.referee.name}</span>}
        {fixture.home_team?.form && (
          <span>H: {parseForm(fixture.home_team.form).map((f, i) => <span key={i} className={f.colour}>{f.letter}</span>)}</span>
        )}
      </div>
    </div>
  );
}
