import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../utils/constants';

/**
 * Fetch team statistics and form data.
 * @param {number|null} teamId
 */
export default function useTeamStats(teamId) {
  const [stats, setStats] = useState(null);
  const [form, setForm] = useState(null);
  const [matches, setMatches] = useState([]);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!teamId) return;

    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const [statsRes, formRes, matchesRes, playersRes] = await Promise.all([
          axios.get(`${API_BASE}/teams/${teamId}/stats`),
          axios.get(`${API_BASE}/teams/${teamId}/form`),
          axios.get(`${API_BASE}/teams/${teamId}/matches?limit=20`),
          axios.get(`${API_BASE}/teams/${teamId}/players`),
        ]);
        setStats(statsRes.data);
        setForm(formRes.data);
        setMatches(matchesRes.data.matches || []);
        setPlayers(playersRes.data.players || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [teamId]);

  return { stats, form, matches, players, loading, error };
}
