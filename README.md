# Game Picker

Estimate how long **you** are likely to stick with a game — starting from an
average-player baseline, then adjusting with your preferences, recent genres,
and weekly free time.

The scoring model started from the
[Factory Game Reviews](https://docs.google.com/spreadsheets/d/1Ri_fVBqFZL5VwGyyKAg2WYtw54rgRRWldSOx-vQRDmM/edit)
spreadsheet and the same interpretable formula scores the broader Steam library
(with documented proxies where factory-only fields are missing).

## Quick start — web UI

```bash
pip install -r requirements.txt
python3 -m game_picker serve
# open http://127.0.0.1:8765/
```

1. Open **Your play profile** — liked/avoided genres, recent games & genres,
   pacing, completionism, solo↔MP, complexity, and **weekly free time**.
2. Search a title to see **your personalized hours** next to the **average-player
   baseline**, an adjusted addictiveness grade, calendar weeks/months at your
   weekly budget, and the reasons for the adjustment.

Profile choices persist in `sessionStorage` for the browser tab.

## Quick start — CLI

```bash
python3 -m game_picker score -v
python3 -m game_picker score-one \
  --game "Example Factory" \
  --scaled-median 80 --scaled-avg 160 --avg-last-2w 8 \
  --pct-active 0.35 --pct-100h 0.40 --peak-players 4000 -v
```

Required feature keys: `game`, `scaled_median_playtime_h`,
`scaled_avg_playtime_h`, `avg_last_2w_h`, `pct_active_last_2w`,
`pct_100h_plus`, `peak_players`.

## Data

| Path | Role |
|------|------|
| `data/factory-game-reviews.xlsx` | Factory workbook (source of truth for those 11 titles) |
| `data/factory_game_features.csv` | Clean factory per-game features |
| `data/game_library.json` | ~1000-game scored library (full provenance) |
| `data/game_library.csv` | Flat table for spreadsheets |
| `web/games.json` | Slim bundle loaded by the UI |
| `web/` | Static searchable interface |

### Library sources

1. **Steam (≈989 titles)** — curated from the public
   [FronkonGames/steam-games-dataset](https://huggingface.co/datasets/FronkonGames/steam-games-dataset)
   on Hugging Face (SteamSpy-derived `average`/`median` playtime forever &
   2-week fields, plus `peak_ccu`, genres, header art). Popularity-ranked after
   filtering playtests/soundtracks/demos and requiring non-zero median playtime.
2. **Factory reviews (11 titles)** — spreadsheet reviewer samples override the
   Steam row when present (`confidence: high`).

### Mapping Steam → model features

| Model feature | Steam mapping | Confidence |
|---------------|---------------|------------|
| `scaled_median_playtime_h` | `median_playtime_forever / 60` (no age scale available) | medium |
| `scaled_avg_playtime_h` | `average_playtime_forever / 60` | medium |
| `avg_last_2w_h` | `average_playtime_2weeks / 60` | medium |
| `pct_active_last_2w` | **Proxy:** `0.04 + 0.70*(avg2w/(avg2w+8)) + 0.16*log_norm(peak_ccu)` | low |
| `pct_100h_plus` | **Proxy:** lognormal tail `P(X≥100)` from mean & median | low |
| `peak_players` | dataset `peak_ccu` | medium |

Rebuild (needs the HF parquet locally + `pandas`/`pyarrow`):

```bash
pip install pandas pyarrow
python3 scripts/build_library.py --parquet /path/to/games.parquet --limit 1000
```

### Caveats

- SteamSpy-style stats are **all-owner** averages/medians — usually lower than
  the factory **reviewer-only** samples for the same game.
- Stickiness (`pct_active`) and deep-hook (`pct_100h_plus`) are **proxies** on
  Steam rows; the UI labels them as mixed confidence.
- Peak CCU is a dataset snapshot, not necessarily all-time peak.
- “Addictiveness” means engagement signals, not clinical addiction or quality.
- Library membership is popularity-biased; obscure niche titles may be absent.

## Model

### Addictiveness (0–100, letter grades)

| Component | Weight | Signal |
|-----------|--------|--------|
| `depth` | 30% | Median playtime (log-normalized) |
| `intensity` | 25% | Mean playtime last 2 weeks (log-normalized) |
| `stickiness` | 25% | % active last 2 weeks (or proxy) |
| `deep_hook` | 15% | % with ≥100 hours (or proxy) |
| `popularity` | 5% | Peak concurrent players (log-normalized) |

Grades: **S** ≥ 85, **A** ≥ 75, **B** ≥ 65, **C** ≥ 50, **D** ≥ 35, else **F**.

### Average-player playtime (hours)

```text
capped_avg = min(scaled_avg, scaled_median × 2.2)
hours = (0.70 × scaled_median + 0.30 × capped_avg)
        × (1 + 0.12 × stickiness_component)
```

See `game_picker/model.py`.

## Personalization (fair calibration)

Baseline scores stay as above. A user profile then applies **clamped,
documented multipliers** (`game_picker/personalize.py`, mirrored in
`web/personalize.js`):

1. **Affinity** ∈ [-1, 1] from liked/disliked/recent genre overlap (+ small
   familiarity boost if the title appears in “games played recently”). Thin
   genre metadata mutes affinity.
2. **Fit terms** (0–1): pacing vs depth, complexity tolerance vs game
   complexity, multiplayer bias vs Steam categories.
3. **Hours multiplier** (clamped **0.50–1.55**):

```text
hours_mult = 1
  + 0.35·affinity
  + 0.15·(pacing_fit−0.5)·2
  + 0.12·(complexity_fit−0.5)·2
  + 0.10·(mp_fit−0.5)·2
  + 0.10·(completionism−0.5)·2

H_pref = H_avg × hours_mult
```

4. **Weekly free time** sets a calendar horizon (about 4–26 weeks, longer when
   the baseline hook and affinity are high / completionism is high):

```text
H_you = min(H_pref, weekly_hours × horizon_weeks)
weeks ≈ H_you / weekly_hours
```

Addictiveness shifts modestly with affinity/fits and is re-graded. The UI
always shows **your estimate vs average**.

## Sample estimates (checked-in library)

| Game | Est. hours | Grade | Source |
|------|----------:|:-----:|--------|
| Factorio | 158.6 | A | factory |
| Counter-Strike 2 | 154.3 | A | steam |
| ELDEN RING | 117.1 | B | steam |
| Baldur's Gate 3 | 100.3 | B | steam |
| Cyberpunk 2077 | 66.8 | C | steam |
| Terraria | 50.3 | C | steam |
| Stardew Valley | 42.2 | D | steam |
| Hades | 24.1 | F | steam |
| Celeste | 7.2 | F | steam |

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
