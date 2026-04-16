import { useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE, STAKE } from '../utils/constants';

/**
 * Accumulator builder state management.
 * Tracks selected legs, calculates running odds, handles save.
 */
export default function useAccumulator() {
  const [legs, setLegs] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const addLeg = useCallback((leg) => {
    setLegs((prev) => {
      // Don't allow duplicate matches
      if (prev.some((l) => l.match_id === leg.match_id)) {
        // Replace existing selection for that match
        return prev.map((l) => (l.match_id === leg.match_id ? leg : l));
      }
      return [...prev, leg];
    });
  }, []);

  const removeLeg = useCallback((matchId) => {
    setLegs((prev) => prev.filter((l) => l.match_id !== matchId));
  }, []);

  const clearLegs = useCallback(() => {
    setLegs([]);
  }, []);

  const combinedOdds = legs.reduce((acc, leg) => acc * (leg.odds || 1), 1);
  const ourProbability = legs.reduce((acc, leg) => acc * (leg.our_probability || 0), legs.length > 0 ? 1 : 0);
  const potentialReturn = combinedOdds * STAKE;
  const hasNegativeEdge = legs.some((leg) => (leg.edge_pct || 0) < 0);

  const saveAccumulator = useCallback(async (targetOdds, notes = '') => {
    if (legs.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const today = new Date().toISOString().split('T')[0];
      await axios.post(`${API_BASE}/accumulator/save`, {
        slate_date: today,
        legs: legs.map((l) => ({
          match_id: l.match_id,
          home_team: l.home_team,
          away_team: l.away_team,
          selection: l.selection,
          odds: l.odds,
          our_probability: l.our_probability,
          edge_pct: l.edge_pct,
        })),
        target_odds: targetOdds,
        actual_odds: combinedOdds,
        our_probability: ourProbability,
        stake: STAKE,
        potential_return: potentialReturn,
        notes,
      });
      clearLegs();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }, [legs, combinedOdds, ourProbability, potentialReturn, clearLegs]);

  return {
    legs,
    addLeg,
    removeLeg,
    clearLegs,
    combinedOdds,
    ourProbability,
    potentialReturn,
    hasNegativeEdge,
    saveAccumulator,
    saving,
    error,
  };
}
