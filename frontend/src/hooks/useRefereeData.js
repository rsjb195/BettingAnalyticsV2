import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../utils/constants';

/**
 * Fetch referee profile, match log, and impact data.
 * @param {number|null} refereeId
 */
export default function useRefereeData(refereeId) {
  const [profile, setProfile] = useState(null);
  const [matchLog, setMatchLog] = useState([]);
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!refereeId) return;

    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const [profileRes, matchesRes, impactRes] = await Promise.all([
          axios.get(`${API_BASE}/referees/${refereeId}/profile`),
          axios.get(`${API_BASE}/referees/${refereeId}/matches?limit=30`),
          axios.get(`${API_BASE}/referees/${refereeId}/impact`),
        ]);
        setProfile(profileRes.data);
        setMatchLog(matchesRes.data.matches || []);
        setImpact(impactRes.data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [refereeId]);

  return { profile, matchLog, impact, loading, error };
}
