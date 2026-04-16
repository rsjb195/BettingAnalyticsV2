import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../utils/constants';

/**
 * Fetch the Saturday slate data.
 */
export default function useSlate() {
  const [slate, setSlate] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSlate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API_BASE}/matches/saturday-slate`);
      setSlate(res.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSlate();
  }, []);

  return { slate, loading, error, refresh: fetchSlate };
}
