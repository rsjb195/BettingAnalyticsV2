import { NavLink } from 'react-router-dom';
import { NAV_ITEMS } from '../../utils/constants';
import {
  LayoutDashboard, Calendar, Layers, Trophy, Shield, Users,
  UserCheck, BarChart3, TrendingUp, DollarSign, ClipboardList,
} from 'lucide-react';

const ICON_MAP = {
  LayoutDashboard, Calendar, Layers, Trophy, Shield, Users,
  UserCheck, BarChart3, TrendingUp, DollarSign, ClipboardList,
};

export default function Sidebar() {
  return (
    <aside className="w-60 flex-shrink-0 bg-terminal-bg-secondary border-r border-terminal-border flex flex-col">
      {/* Logo / Title */}
      <div className="h-14 flex items-center px-5 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-accent-cyan glow-cyan" />
          <span className="font-data text-sm font-bold text-accent-cyan tracking-wider">
            QUANT
          </span>
          <span className="font-data text-sm font-bold text-text-primary tracking-wider">
            FOOTBALL
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {NAV_ITEMS.map((section) => (
          <div key={section.section} className="mb-4">
            <div className="px-5 mb-2">
              <span className="text-[10px] font-data font-semibold text-text-muted tracking-[0.15em] uppercase">
                {section.section}
              </span>
            </div>
            {section.items.map((item) => {
              const Icon = ICON_MAP[item.icon];
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-5 py-2 text-sm transition-colors ${
                      isActive
                        ? 'text-accent-cyan bg-accent-cyan/5 border-r-2 border-accent-cyan'
                        : 'text-text-secondary hover:text-text-primary hover:bg-terminal-elevated/30'
                    }`
                  }
                >
                  {Icon && <Icon size={16} strokeWidth={1.5} />}
                  <span className="font-ui">{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-terminal-border">
        <div className="text-[10px] font-data text-text-muted">
          v1.0.0 | Dixon-Coles
        </div>
        <div className="text-[10px] font-data text-text-muted mt-0.5">
          $50 fixed stake
        </div>
      </div>
    </aside>
  );
}
