import { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import useSlate from '../hooks/useSlate';
import useAccumulator from '../hooks/useAccumulator';
import StatCard from '../components/shared/StatCard';
import OddsBadge from '../components/shared/OddsBadge';
import EdgeIndicator from '../components/shared/EdgeIndicator';
import { formatPct, formatOdds, formatCurrency, parseForm } from '../utils/formatters';
import { STAKE } from '../utils/constants';

export default function SlatePage() {
  const { slate, loading, error, refresh } = useSlate();
  const acca = useAccumulator();
  const [targetOdds, setTargetOdds] = useState(25);

  const fixtures = slate?.fixtures || [];

  const handleSelectOutcome = (fixture, outcome) => {
    const model = fixture.model || {};
    const oddsMap = { home: fixture.odds?.home, draw: fixture.odds?.draw, away: fixture.odds?.away };
    const probMap = { home: model.our_home_prob, draw: model.our_draw_prob, away: model.our_away_prob };
    const edgeMap = { home: model.home_edge, draw: model.draw_edge, away: model.away_edge };

    acca.addLeg({
      match_id: fixture.match_id,
      home_team: fixture.home_team?.name || '?',
      away_team: fixture.away_team?.name || '?',
      selection: outcome,
      odds: oddsMap[outcome] || 1,
      our_probability: probMap[outcome] || 0,
      edge_pct: edgeMap[outcome] || 0,
    });
  };

  return (
    <div className="flex gap-6 h-full">
      {/* Left: Fixture grid */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-ui font-bold text-accent-cyan uppercase tracking-wider">
              Saturday 3PM Slate
            </h2>
            <span className="text-xs font-data text-text-muted">
              {slate?.slate_date || '—'} | {fixtures.length} fixtures
            </span>
          </div>
          <button onClick={refresh} className="btn-primary text-xs">Refresh</button>
        </div>

        {loading && <div className="text-text-muted font-data text-sm py-8 text-center">Loading slate...</div>}
        {error && <div className="text-accent-red font-data text-sm py-4">Error: {error}</div>}

        {/* Fixture cards */}
        {fixtures.map((f) => {
          const model = f.model || {};
          const bestEdge = Math.max(model.home_edge || 0, model.draw_edge || 0, model.away_edge || 0);
          const selectedLeg = acca.legs.find((l) => l.match_id === f.match_id);

          return (
            <div key={f.match_id} className="stat-card-accent space-y-3">
              {/* Teams + league */}
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-ui font-semibold text-text-primary">
                    {f.home_team?.name || '?'}
                  </span>
                  <span className="text-text-muted mx-2">vs</span>
                  <span className="text-sm font-ui font-semibold text-text-primary">
                    {f.away_team?.name || '?'}
                  </span>
                </div>
                <EdgeIndicator edge={bestEdge} showLabel />
              </div>

              {/* Odds row — clickable to add to accumulator */}
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="text-[10px] font-data text-text-muted mb-1">HOME</div>
                  <OddsBadge
                    odds={f.odds?.home}
                    edge={model.home_edge}
                    selected={selectedLeg?.selection === 'home'}
                    onClick={() => handleSelectOutcome(f, 'home')}
                  />
                  {model.our_home_prob && (
                    <div className="text-[10px] font-data text-text-muted mt-1">
                      Our: {formatPct(model.our_home_prob)}
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <div className="text-[10px] font-data text-text-muted mb-1">DRAW</div>
                  <OddsBadge
                    odds={f.odds?.draw}
                    edge={model.draw_edge}
                    selected={selectedLeg?.selection === 'draw'}
                    onClick={() => handleSelectOutcome(f, 'draw')}
                  />
                  {model.our_draw_prob && (
                    <div className="text-[10px] font-data text-text-muted mt-1">
                      Our: {formatPct(model.our_draw_prob)}
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <div className="text-[10px] font-data text-text-muted mb-1">AWAY</div>
                  <OddsBadge
                    odds={f.odds?.away}
                    edge={model.away_edge}
                    selected={selectedLeg?.selection === 'away'}
                    onClick={() => handleSelectOutcome(f, 'away')}
                  />
                  {model.our_away_prob && (
                    <div className="text-[10px] font-data text-text-muted mt-1">
                      Our: {formatPct(model.our_away_prob)}
                    </div>
                  )}
                </div>
              </div>

              {/* Context row */}
              <div className="flex items-center gap-6 text-[10px] font-data text-text-muted">
                {f.referee && (
                  <span>
                    REF: {f.referee.name}
                    {f.referee.avg_cards && (
                      <span className={f.referee.avg_cards > 4.5 ? 'text-accent-red ml-1' : 'ml-1'}>
                        ({f.referee.avg_cards.toFixed(1)} cards/m)
                      </span>
                    )}
                    {f.referee.home_bias && f.referee.home_bias > 1.2 && (
                      <span className="text-accent-amber ml-1">[HOME BIAS]</span>
                    )}
                  </span>
                )}
                {f.home_team?.form && (
                  <span>
                    H FORM:{' '}
                    {parseForm(f.home_team.form).map((ch, i) => (
                      <span key={i} className={ch.colour}>{ch.letter}</span>
                    ))}
                  </span>
                )}
                {f.away_team?.form && (
                  <span>
                    A FORM:{' '}
                    {parseForm(f.away_team.form).map((ch, i) => (
                      <span key={i} className={ch.colour}>{ch.letter}</span>
                    ))}
                  </span>
                )}
              </div>
            </div>
          );
        })}

        {!loading && fixtures.length === 0 && (
          <div className="stat-card text-center py-12">
            <span className="text-text-muted font-data text-sm">No Saturday fixtures found for the upcoming slate.</span>
          </div>
        )}
      </div>

      {/* Right: Accumulator Builder */}
      <div className="w-80 flex-shrink-0 bg-terminal-bg-secondary border-l border-terminal-border p-4 flex flex-col overflow-y-auto">
        <h3 className="text-sm font-data font-bold text-accent-cyan uppercase tracking-wider mb-4">
          Accumulator Builder
        </h3>

        {/* Target odds buttons */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setTargetOdds(25)}
            className={`flex-1 py-1.5 text-xs font-data border ${
              targetOdds === 25 ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10' : 'border-terminal-border text-text-muted'
            }`}
          >
            25/1
          </button>
          <button
            onClick={() => setTargetOdds(40)}
            className={`flex-1 py-1.5 text-xs font-data border ${
              targetOdds === 40 ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10' : 'border-terminal-border text-text-muted'
            }`}
          >
            40/1
          </button>
        </div>

        {/* Legs list */}
        <div className="flex-1 space-y-2 mb-4">
          {acca.legs.length === 0 && (
            <div className="text-text-muted text-xs font-data py-4 text-center">
              Click odds on fixtures to add legs
            </div>
          )}
          {acca.legs.map((leg) => (
            <div key={leg.match_id} className="bg-terminal-card border border-terminal-border p-2 flex items-center justify-between">
              <div>
                <div className="text-xs font-data text-text-primary">
                  {leg.home_team} v {leg.away_team}
                </div>
                <div className="text-[10px] font-data text-text-muted mt-0.5">
                  {leg.selection.toUpperCase()} @ {formatOdds(leg.odds)} |{' '}
                  <span className={leg.edge_pct > 0 ? 'text-accent-green' : 'text-accent-red'}>
                    Edge: {(leg.edge_pct * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              <button onClick={() => acca.removeLeg(leg.match_id)} className="text-text-muted hover:text-accent-red">
                <X size={14} />
              </button>
            </div>
          ))}
        </div>

        {/* Running totals */}
        {acca.legs.length > 0 && (
          <div className="space-y-3 border-t border-terminal-border pt-4">
            <div className="flex justify-between text-xs font-data">
              <span className="text-text-muted">Combined Odds</span>
              <span className="text-text-primary font-bold">{formatOdds(acca.combinedOdds)}</span>
            </div>
            <div className="flex justify-between text-xs font-data">
              <span className="text-text-muted">Win Probability</span>
              <span className="text-text-secondary">{formatPct(acca.ourProbability)}</span>
            </div>
            <div className="flex justify-between text-xs font-data">
              <span className="text-text-muted">Stake</span>
              <span className="text-text-secondary">{formatCurrency(STAKE)}</span>
            </div>

            {/* Potential return — large */}
            <div className="bg-terminal-elevated border border-accent-cyan/20 p-3 text-center">
              <div className="text-[10px] font-data text-text-muted uppercase tracking-wider">Potential Return</div>
              <div className="text-2xl font-data font-bold text-accent-green mt-1">
                {formatCurrency(acca.potentialReturn)}
              </div>
            </div>

            {/* Warnings */}
            {acca.hasNegativeEdge && (
              <div className="flex items-center gap-2 text-xs font-data text-accent-amber bg-accent-amber/5 border border-accent-amber/20 p-2">
                <AlertTriangle size={14} />
                <span>One or more legs have negative edge</span>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2">
              <button onClick={() => acca.saveAccumulator(targetOdds)} disabled={acca.saving} className="flex-1 btn-success text-xs">
                {acca.saving ? 'Saving...' : 'Save Accumulator'}
              </button>
              <button onClick={acca.clearLegs} className="btn-danger text-xs">
                Clear
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
