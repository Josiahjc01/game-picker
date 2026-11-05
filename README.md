# game-picker

Score factory/automation games for **addictiveness** and estimate how long an
**average player** will stick around, using Steam-style reviewer playtime data
from the [Factory Game Reviews](https://docs.google.com/spreadsheets/d/1Ri_fVBqFZL5VwGyyKAg2WYtw54rgRRWldSOx-vQRDmM/edit) spreadsheet.

## Quick start

```bash
pip install -r requirements.txt
python3 -m game_picker score
python3 -m game_picker score -v          # show component breakdown
python3 -m game_picker score --json      # machine-readable
```

Score a new game with the same feature inputs:

```bash
python3 -m game_picker score-one \
  --game "Example Factory" \
  --scaled-median 80 \
  --scaled-avg 160 \
  --avg-last-2w 8 \
  --pct-active 0.35 \
  --pct-100h 0.40 \
  --peak-players 4000 \
  -v
```

Required keys (also via `python3 -m game_picker feature-keys`):

`game`, `scaled_median_playtime_h`, `scaled_avg_playtime_h`, `avg_last_2w_h`,
`pct_active_last_2w`, `pct_100h_plus`, `peak_players`.

Rebuild the checked-in feature table from the workbook:

```bash
python3 -m game_picker build-features
# or: python3 scripts/build_features.py
```

## Data

| Path | Role |
|------|------|
| `data/factory-game-reviews.xlsx` | Source workbook (Graphs + per-game review sheets) |
| `data/factory_game_features.csv` | Clean per-game features used for scoring |
| `data/factory_game_features.json` | Same features as JSON |

The Graphs tab is charts-only / duplicated layout. Real metrics live on the
per-game sheets (`Fa`, `Mind`, `S1`, …): raw + age-scaled averages/medians,
last-two-week playtime, days since release, and ~1k reviewer samples each.
Peak concurrent players are pulled from the Graphs summary block.

### Caveats

- Samples are recent Steam reviewers (~1k/game), not a random player census;
  they skew toward people engaged enough to leave a review.
- Age-scaled playtime uses the spreadsheet’s days-since-release correction;
  brand-new titles can look inflated vs. decade-old ones.
- Peak players are a single snapshot (2026-03-16 in this export) and can be
  launch- or sale-boosted.
- “Addictiveness” here means sustained engagement signals, not clinical
  addiction and not a quality/recommend rating.

## Model

### Addictiveness (0–100, letter grades)

Interpretable weighted sum of five normalized components (fixed factory-genre
anchors so new games score without re-fitting the cohort):

| Component | Weight | Signal |
|-----------|--------|--------|
| `depth` | 30% | Age-adjusted median playtime (log-normalized) |
| `intensity` | 25% | Mean playtime last 2 weeks (log-normalized) |
| `stickiness` | 25% | % of reviewers with any last-2-week playtime |
| `deep_hook` | 15% | % of reviewers with ≥100 hours |
| `popularity` | 5% | Peak concurrent players (log-normalized) |

Grades: **S** ≥ 85, **A** ≥ 75, **B** ≥ 65, **C** ≥ 50, **D** ≥ 35, else **F**.

### Average-player playtime (hours)

Means are whale-skewed, so the estimator anchors on the age-adjusted median and
blends a capped mean, with a small uplift when stickiness is high:

```text
capped_avg = min(scaled_avg, scaled_median × 2.2)
hours = (0.70 × scaled_median + 0.30 × capped_avg)
        × (1 + 0.12 × stickiness_component)
```

Formulas live in `game_picker/model.py` and are intentionally transparent
rather than opaque ML.

## Library usage

```python
from game_picker import score_game

result = score_game({
    "game": "Factorio",
    "scaled_median_playtime_h": 106.3,
    "scaled_avg_playtime_h": 302.7,
    "avg_last_2w_h": 22.4,
    "pct_active_last_2w": 0.65,
    "pct_100h_plus": 0.60,
    "peak_players": 22007,
})
print(result.addictiveness, result.grade, result.estimated_avg_player_hours)
```
