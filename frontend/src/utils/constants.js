/**
 * Application constants.
 */

export const API_BASE = '/api';

export const STAKE = 50;

export const TIER_NAMES = {
  1: 'Premier League',
  2: 'Championship',
  3: 'League One',
  4: 'League Two',
};

export const NAV_ITEMS = [
  {
    section: 'OVERVIEW',
    items: [
      { label: 'Dashboard', path: '/', icon: 'LayoutDashboard' },
      { label: 'Saturday Slate', path: '/slate', icon: 'Calendar' },
      { label: 'Accumulator Builder', path: '/accumulator', icon: 'Layers' },
    ],
  },
  {
    section: 'RESEARCH',
    items: [
      { label: 'Leagues', path: '/leagues', icon: 'Trophy' },
      { label: 'Teams', path: '/teams', icon: 'Shield' },
      { label: 'Players', path: '/players', icon: 'Users' },
      { label: 'Referees', path: '/referees', icon: 'UserCheck' },
    ],
  },
  {
    section: 'MODELS',
    items: [
      { label: 'Match Probabilities', path: '/model/outputs', icon: 'BarChart3' },
      { label: 'Edge Finder', path: '/model/edge', icon: 'TrendingUp' },
    ],
  },
  {
    section: 'PERFORMANCE',
    items: [
      { label: 'P&L Tracker', path: '/performance', icon: 'DollarSign' },
      { label: 'Selection Log', path: '/accumulator/log', icon: 'ClipboardList' },
    ],
  },
];
