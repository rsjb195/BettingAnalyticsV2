import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Wifi, WifiOff } from 'lucide-react';

const PAGE_TITLES = {
  '/': 'Dashboard',
  '/slate': 'Saturday Slate',
  '/accumulator': 'Accumulator Builder',
  '/leagues': 'Leagues',
  '/teams': 'Teams',
  '/players': 'Players',
  '/referees': 'Referees',
  '/model/outputs': 'Match Probabilities',
  '/model/edge': 'Edge Finder',
  '/performance': 'P&L Tracker',
  '/accumulator/log': 'Selection Log',
};

export default function TopNav() {
  const location = useLocation();
  const [ukTime, setUkTime] = useState('');
  const [apiStatus, setApiStatus] = useState('unknown');
  const [lastRefresh, setLastRefresh] = useState(null);

  // Live UK clock — updates every second
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const ukStr = now.toLocaleString('en-GB', {
        timeZone: 'Europe/London',
        weekday: 'short',
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
      setUkTime(ukStr);
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // API health check — every 30 seconds
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch('/api/health');
        if (res.ok) {
          setApiStatus('connected');
          setLastRefresh(new Date().toISOString());
        } else {
          setApiStatus('error');
        }
      } catch {
        setApiStatus('disconnected');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const title = PAGE_TITLES[location.pathname] || 'Dashboard';
  const statusDot =
    apiStatus === 'connected' ? 'bg-accent-green' :
    apiStatus === 'error' ? 'bg-accent-amber' :
    'bg-accent-red';

  return (
    <header className="h-14 flex-shrink-0 bg-terminal-bg-secondary border-b border-terminal-border flex items-center justify-between px-6">
      {/* Page title */}
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-ui font-semibold text-text-primary">
          {title}
        </h1>
      </div>

      {/* Right side: clock, refresh, status */}
      <div className="flex items-center gap-6">
        {/* Last data refresh */}
        {lastRefresh && (
          <div className="text-xs font-data text-text-muted">
            REFRESH: {new Date(lastRefresh).toLocaleTimeString('en-GB', {
              hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London',
            })}
          </div>
        )}

        {/* API status */}
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${statusDot}`} />
          {apiStatus === 'connected' ? (
            <Wifi size={14} className="text-accent-green" />
          ) : (
            <WifiOff size={14} className="text-accent-red" />
          )}
        </div>

        {/* UK time */}
        <div className="font-data text-sm text-accent-cyan tabular-nums">
          {ukTime}
        </div>
      </div>
    </header>
  );
}
