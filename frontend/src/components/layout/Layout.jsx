import Sidebar from './Sidebar';
import TopNav from './TopNav';
import Ticker from './Ticker';

/**
 * Persistent application shell.
 * Fixed sidebar (left, 240px), top nav, bottom ticker, scrollable main content.
 */
export default function Layout({ children }) {
  return (
    <div className="h-screen w-screen flex overflow-hidden bg-terminal-bg">
      {/* Sidebar */}
      <Sidebar />

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top nav */}
        <TopNav />

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>

        {/* Ticker tape */}
        <Ticker />
      </div>
    </div>
  );
}
