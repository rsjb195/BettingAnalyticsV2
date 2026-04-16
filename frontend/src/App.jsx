import { Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import DashboardPage from './pages/DashboardPage';
import SlatePage from './pages/SlatePage';
import TeamsPage from './pages/TeamsPage';
import PlayersPage from './pages/PlayersPage';
import RefereesPage from './pages/RefereesPage';
import LeaguePage from './pages/LeaguePage';
import PerformancePage from './pages/PerformancePage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/slate" element={<SlatePage />} />
        <Route path="/accumulator" element={<SlatePage />} />
        <Route path="/leagues" element={<LeaguePage />} />
        <Route path="/leagues/:leagueId" element={<LeaguePage />} />
        <Route path="/teams" element={<TeamsPage />} />
        <Route path="/teams/:teamId" element={<TeamsPage />} />
        <Route path="/players" element={<PlayersPage />} />
        <Route path="/players/:playerId" element={<PlayersPage />} />
        <Route path="/referees" element={<RefereesPage />} />
        <Route path="/referees/:refereeId" element={<RefereesPage />} />
        <Route path="/model/outputs" element={<DashboardPage />} />
        <Route path="/model/edge" element={<DashboardPage />} />
        <Route path="/performance" element={<PerformancePage />} />
        <Route path="/accumulator/log" element={<PerformancePage />} />
      </Routes>
    </Layout>
  );
}
