import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft } from 'lucide-react';
import EdgeIndicator from '../components/shared/EdgeIndicator';
import { API_BASE } from '../utils/constants';
import { formatDate, formatOdds, formatPct } from '../utils/formatters';

function StatBar({ label, home, away, format = (v) => v ?? '—' }) {
  const total = (home ?? 0) + (away ?? 0);
  const homePct = total > 0 ? ((home ?? 0) / total) * 100 : 50;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] font-data text-text-muted">
        <span>{format(home)}</span>
        <span className="uppercase tracking-wider text-center">{label}</span>
        <span>{format(away)}</span>
      </div>
      <div className="flex h-1.5 rounded-none overflow-hidden">
        <div className="bg-accent-cyan transition-all" style={{ width: `${homePct}%` }} />
        <div className="bg-terminal-border flex-1" />
      </div>
    </div>
  );
}

function StatRow({ label, home, away }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-terminal-border/20 text-xs font-data">
      <span className="tabular-nums text-text-primary w-10 text-left">{home ?? '—'}</span>
      <span className="text-text-muted uppercase tracking-wider text-[10px] text-center flex-1">{label}</span>
      <span className="tabular-nums text-text-primary w-10 text-right">{away ?? '—'}</span>
    </div>
  );
}

export default function MatchDetailPage() {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const [match, setMatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API_BASE}/matches/${matchId}`)
      .then((r) => setMatch(r.data))
      .catch(() => setError('Match not found'))
      .finally(() => setLoading(false));
  }, [matchId]);

  if (loading) return <div className="text-text-muted font-data text-sm py-12 text-center">Loading match...</div>;
  if (error || !match) return <div className="text-accent-red font-data text-sm py-12 text-center">{error || 'Match not found'}</div>;

  const mo = match.model_output;
  const hasResult = match.home_goals != null && match.away_goals != null;
  const hasStats = match.home_shots != null || match.home_possession != null || match.home_xg != null;

  return (
    <div className="space-y-5 max-w-3xl mx-auto">
      {/* Back */}
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-xs font-data text-text-muted hover:text-text-primary transition-colors">
        <ArrowLeft size={14} /> Back
      </button>

      {/* Match header */}
      <div className="stat-card">
        <div className="text-[10px] font-data text-text-muted uppercase tracking-wider mb-3">
          {formatDate(match.match_date)} · GW{match.game_week || '?'} · {match.season}
        </div>

        {/* Score / teams */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 text-right">
            <div className="text-lg font-ui font-bold text-text-primary">{match.home_team_name}</div>
            {mo && <div className="text-[10px] font-data text-text-muted mt-1">Our prob: {formatPct(mo.our_home_prob)}</div>}
          </div>

          <div className="text-center px-4">
            {hasResult ? (
              <>
                <div className="text-3xl font-data font-bold text-text-primary tabular-nums">
                  {match.home_goals} – {match.away_goals}
                </div>
                {match.home_goals_ht != null && (
                  <div className="text-[10px] font-data text-text-muted mt-1">
                    HT: {match.home_goals_ht} – {match.away_goals_ht}
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm font-data text-text-muted uppercase tracking-widest">vs</div>
            )}
          </div>

          <div className="flex-1 text-left">
            <div className="text-lg font-ui font-bold text-text-primary">{match.away_team_name}</div>
            {mo && <div className="text-[10px] font-data text-text-muted mt-1">Our prob: {formatPct(mo.our_away_prob)}</div>}
          </div>
        </div>

        {/* Referee + stadium */}
        {(match.referee_name || match.stadium) && (
          <div className="mt-3 text-[10px] font-data text-text-muted flex gap-4 justify-center">
            {match.referee_name && <span>REF: {match.referee_name}</span>}
            {match.stadium && <span>@ {match.stadium}</span>}
            {match.attendance && <span>{match.attendance.toLocaleString('en-GB')} att.</span>}
          </div>
        )}
      </div>

      {/* Model vs Market */}
      {mo && (
        <div className="stat-card">
          <h3 className="text-xs font-data font-semibold text-text-muted uppercase tracking-wider mb-4">
            Model vs Market
          </h3>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Home Win', prob: mo.our_home_prob, mktOdds: match.odds_home, edge: mo.home_edge },
              { label: 'Draw', prob: mo.our_draw_prob, mktOdds: match.odds_draw, edge: mo.draw_edge },
              { label: 'Away Win', prob: mo.our_away_prob, mktOdds: match.odds_away, edge: mo.away_edge },
            ].map(({ label, prob, mktOdds, edge }) => (
              <div key={label} className="bg-terminal-elevated border border-terminal-border p-3 text-center space-y-2">
                <div className="text-[10px] font-data text-text-muted uppercase tracking-wider">{label}</div>
                <div className="text-xl font-data font-bold text-text-primary">{formatPct(prob)}</div>
                <div className="text-[10px] font-data text-text-muted">Mkt: {formatOdds(mktOdds)}</div>
                {edge != null && <EdgeIndicator edge={edge} showLabel />}
              </div>
            ))}
          </div>
          {mo.best_value && mo.best_value !== 'none' && (
            <div className="mt-3 text-[10px] font-data text-accent-green text-center">
              Best value: {mo.best_value.toUpperCase()} · Confidence: {mo.confidence?.toFixed(1)}/10
            </div>
          )}
        </div>
      )}

      {/* Match stats */}
      {hasStats && (
        <div className="stat-card">
          <div className="flex justify-between text-[10px] font-data text-text-muted uppercase tracking-wider mb-4">
            <span>{match.home_team_name}</span>
            <span>Match Stats</span>
            <span>{match.away_team_name}</span>
          </div>
          <div className="space-y-2">
            {match.home_xg != null && (
              <StatBar label="xG" home={match.home_xg} away={match.away_xg} format={(v) => v?.toFixed(2) ?? '—'} />
            )}
            {match.home_possession != null && (
              <StatBar label="Possession %" home={match.home_possession} away={match.away_possession} format={(v) => v != null ? `${v}%` : '—'} />
            )}
            {match.home_shots != null && (
              <StatBar label="Shots" home={match.home_shots} away={match.away_shots} />
            )}
            {match.home_shots_on_target != null && (
              <StatBar label="Shots on Target" home={match.home_shots_on_target} away={match.away_shots_on_target} />
            )}
            <div className="pt-2 space-y-0">
              <StatRow label="Corners" home={match.home_corners} away={match.away_corners} />
              <StatRow label="Fouls" home={match.home_fouls} away={match.away_fouls} />
              <StatRow label="Yellow Cards" home={match.home_yellow_cards} away={match.away_yellow_cards} />
              <StatRow label="Red Cards" home={match.home_red_cards} away={match.away_red_cards} />
            </div>
          </div>
        </div>
      )}

      {/* Pre-match odds */}
      <div className="stat-card">
        <h3 className="text-xs font-data font-semibold text-text-muted uppercase tracking-wider mb-3">
          Pre-match Odds
        </h3>
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: '1 (Home)', v: match.odds_home },
            { label: 'X (Draw)', v: match.odds_draw },
            { label: '2 (Away)', v: match.odds_away },
            { label: 'O2.5', v: match.odds_over25 },
            { label: 'U2.5', v: match.odds_under25 },
            { label: 'BTTS Y', v: match.odds_btts_yes },
          ].filter(x => x.v).map(({ label, v }) => (
            <div key={label} className="text-center">
              <div className="text-[10px] font-data text-text-muted">{label}</div>
              <div className="text-sm font-data font-bold text-text-primary tabular-nums">{formatOdds(v)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
