# Model Methodology

## Dixon-Coles Poisson Model

### Overview
The platform uses a modified Dixon-Coles (1997) bivariate Poisson model to predict football match outcomes. This approach models the number of goals scored by each team as independent Poisson random variables, with a low-score correction factor.

### Attack/Defence Ratings

For each team, we calculate four ratings:
- **attack_home**: Scoring rate at home relative to league average
- **defence_home**: Conceding rate at home relative to league average
- **attack_away**: Scoring rate away relative to league average
- **defence_away**: Conceding rate away relative to league average

Ratings are calculated using time-decay weighted historical data:
```
weight(match) = exp(-0.693 * days_ago / half_life)
```
Default half-life: 180 days (~6 months). This means a match from 6 months ago contributes 50% as much as today's match.

### Goal Expectations

```
lambda_home = attack_home * defence_away * league_avg_goals * home_advantage
lambda_away = attack_away * defence_home * league_avg_goals
```

Default home advantage factor: 1.20 (historically ~1.15-1.25 in English football).

### Dixon-Coles Low-Score Correction

The standard bivariate Poisson assumes independence between home and away goals. Dixon-Coles introduces a correlation parameter rho to correct for the known dependence at low scores:

| Score | Correction |
|-------|-----------|
| 0-0 | 1 - lambda_h * lambda_a * rho |
| 1-0 | 1 + lambda_a * rho |
| 0-1 | 1 + lambda_h * rho |
| 1-1 | 1 - rho |
| Other | 1.0 (no correction) |

Default rho: -0.04 (small negative correlation, reflecting that low-scoring draws are slightly more common than independence predicts).

### Probability Calculation

Match probabilities are calculated by enumerating all scorelines from 0-0 to 10-10:

```
P(h goals, a goals) = Poisson(h; lambda_home) * Poisson(a; lambda_away) * DC_correction
P(home win) = sum of P(h, a) where h > a
P(draw) = sum of P(h, a) where h == a
P(away win) = sum of P(h, a) where h < a
```

### Edge Calculation

```
edge = our_probability - (1 / market_odds)
```

Positive edge indicates we believe the outcome is more likely than the market prices suggest.

### Confidence Rating (1-10 scale)

Based on:
- **Data recency**: More recent data = higher confidence
- **Sample size**: More matches = higher confidence (30+ matches = 8.0, 5 matches = 4.0)
- **Model uncertainty**: Extreme goal expectations reduce confidence

## Referee Impact Model

### Overview
Referees have measurable, persistent behavioural patterns that affect match outcomes. We profile each referee across multiple dimensions and adjust match probabilities accordingly.

### Profile Dimensions

1. **Card Rate** (career vs rolling L20)
   - L20 is more predictive than career average
   - High card rate (>5/match) flagged for player suspension risk

2. **Home/Away Bias**
   - Ratio of home yellows to away yellows
   - Score > 1.15 = home-card bias (disadvantages home team)
   - Score < 0.85 = away-card bias (advantages home team)
   - Probability adjustment: ~1-1.5% shift on 1X2 for strong bias

3. **Game Flow Impact**
   - Over 2.5 rate in referee's matches vs league average
   - If significantly above/below, adjusts totals market expectation

4. **Card Volatility**
   - Standard deviation of cards per match
   - High volatility = unpredictable (reduces confidence)

### Probability Adjustments

Adjustments are small and conservative:
- Strong home bias: home_win -1.5%, away_win +1.0%, draw +0.5%
- Strong away bias: home_win +1.0%, away_win -1.5%, draw +0.5%
- These compound with the base Dixon-Coles probabilities

## Accumulator Construction

### Target Odds
The system targets accumulators in the 25/1 to 40/1 range using a $50 fixed stake.

### Selection Criteria
1. Each leg must have positive edge >= 2%
2. Legs are scored by: edge * confidence_rating
3. Combinations are ranked by expected value: P(win) * potential_return - stake

### Compound Margin
Bookmaker margin compounds across legs. A 5-leg accumulator with 6% margin per leg has an effective compound margin of ~27%. The system explicitly calculates and displays this.

## Assumptions and Limitations

1. **Poisson assumption**: Goals follow a Poisson distribution. In practice, there is overdispersion in football data.
2. **Independence**: Despite the DC correction, some scoreline dependencies may not be captured.
3. **Team constancy**: Ratings assume team strength is relatively stable. Mid-season transfers, managerial changes, or injuries can violate this.
4. **Historical data**: Minimum 5 matches required. Newly promoted teams or early-season predictions have lower confidence.
5. **Referee data**: Not all matches have referee assignments available pre-match. The model falls back to base probabilities when referee data is unavailable.
