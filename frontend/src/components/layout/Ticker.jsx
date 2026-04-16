import { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE } from '../../utils/constants';

/**
 * Fixed bottom ticker tape — scrolling match results and key stats.
 *
 * Smooth CSS animation, continuous loop with no gaps.
 * Colour codes: home win = cyan, away win = amber, draw = white.
 * Pauses on hover for readability.
 */
export default function Ticker() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    const fetchTicker = async () => {
      try {
        const res = await axios.get(`${API_BASE}/ticker`);
        setItems(res.data.items || []);
      } catch {
        // Fallback placeholder items if API is unavailable
        setItems([
          { home_team: 'MAN CITY', away_team: 'ARSENAL', home_goals: 3, away_goals: 1, result_type: 'home_win' },
          { home_team: 'LIVERPOOL', away_team: 'CHELSEA', home_goals: 2, away_goals: 2, result_type: 'draw' },
          { home_team: 'WOLVES', away_team: 'ASTON VILLA', home_goals: 0, away_goals: 1, result_type: 'away_win' },
          { home_team: 'BRENTFORD', away_team: 'BRIGHTON', home_goals: 1, away_goals: 0, result_type: 'home_win' },
          { home_team: 'BURNLEY', away_team: 'SHEFFIELD UTD', home_goals: 1, away_goals: 1, result_type: 'draw' },
        ]);
      }
    };
    fetchTicker();
    const interval = setInterval(fetchTicker, 120000); // refresh every 2min
    return () => clearInterval(interval);
  }, []);

  const colourFor = (type) => {
    switch (type) {
      case 'home_win': return 'text-accent-cyan';
      case 'away_win': return 'text-accent-amber';
      case 'draw': return 'text-text-primary';
      default: return 'text-text-muted';
    }
  };

  const renderItem = (item, idx) => (
    <span key={idx} className="inline-flex items-center">
      <span className={`${colourFor(item.result_type)} font-data text-xs`}>
        {item.home_team}{' '}
        <span className="text-text-primary font-bold">
          {item.home_goals ?? '?'}-{item.away_goals ?? '?'}
        </span>{' '}
        {item.away_team}
        <span className="text-text-muted ml-1">[FT]</span>
      </span>
      <span className="text-accent-cyan/40 mx-4">{'\u25C6'}</span>
    </span>
  );

  // Duplicate items to create seamless loop
  const allItems = items.length > 0 ? items : [];

  return (
    <div className="h-8 flex-shrink-0 bg-[#060608] border-t border-accent-cyan/30 overflow-hidden relative">
      <div className="ticker-track h-full items-center">
        {/* First copy */}
        <div className="flex items-center h-full px-4">
          {allItems.map((item, i) => renderItem(item, `a-${i}`))}
          {/* Intersperse stats */}
          <span className="text-accent-purple/80 font-data text-xs mx-4">
            BTTS PL: 52.3%
          </span>
          <span className="text-accent-cyan/40 mx-2">{'\u25C6'}</span>
          <span className="text-accent-amber/80 font-data text-xs mx-4">
            O2.5 CHAMP: 48.7%
          </span>
          <span className="text-accent-cyan/40 mx-2">{'\u25C6'}</span>
        </div>
        {/* Second copy — creates seamless loop */}
        <div className="flex items-center h-full px-4">
          {allItems.map((item, i) => renderItem(item, `b-${i}`))}
          <span className="text-accent-purple/80 font-data text-xs mx-4">
            BTTS PL: 52.3%
          </span>
          <span className="text-accent-cyan/40 mx-2">{'\u25C6'}</span>
          <span className="text-accent-amber/80 font-data text-xs mx-4">
            O2.5 CHAMP: 48.7%
          </span>
          <span className="text-accent-cyan/40 mx-2">{'\u25C6'}</span>
        </div>
      </div>
    </div>
  );
}
