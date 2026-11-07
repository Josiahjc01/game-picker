"""Interpretable addictiveness + average-player playtime models.

Addictiveness (0–100)
---------------------
Weighted blend of five normalized signals, all derived from Steam-style
reviewer playtime / concurrency snapshots in the factory-game workbook:

  depth      (30%)  age-adjusted median playtime — typical investment
  intensity  (25%)  mean playtime in the last two weeks — ongoing pull
  stickiness (25%)  share of reviewers with any last-2-week playtime
  deep_hook  (15%)  share of reviewers at ≥100 hours — long-tail compulsion
  popularity  (5%)  peak concurrent players — soft social/meta pull

Each signal is mapped to [0, 1] with fixed factory-genre anchors (log for
skewed hours/players, linear for fractions), then scaled to 0–100.
Letter grades: S ≥ 85, A ≥ 75, B ≥ 65, C ≥ 50, D ≥ 35, else F.

Average-player playtime (hours)
-------------------------------
Skewed playtime distributions make the raw mean whale-dominated. The
estimator therefore anchors on the age-adjusted median and blends in a
capped mean, with a small uplift when stickiness is high (players are
still accumulating hours):

  capped_avg = min(scaled_avg, scaled_median * 2.2)
  hours = (0.70 * scaled_median + 0.30 * capped_avg)
          * (1 + 0.12 * stickiness_component)

Age-adjusted (\"scaled\") medians/averages come from the spreadsheet's own
days-since-release correction so newer and older titles are comparable.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping


FEATURE_KEYS = (
    "game",
    "scaled_median_playtime_h",
    "scaled_avg_playtime_h",
    "avg_last_2w_h",
    "pct_active_last_2w",
    "pct_100h_plus",
    "peak_players",
)

WEIGHTS = {
    "depth": 0.30,
    "intensity": 0.25,
    "stickiness": 0.25,
    "deep_hook": 0.15,
    "popularity": 0.05,
}

# Fixed anchors so new games can be scored without the original cohort.
ANCHORS = {
    "depth": (15.0, 200.0),  # scaled median hours
    "intensity": (0.5, 30.0),  # avg last-2-week hours
    "stickiness": (0.03, 0.80),  # fraction active
    "deep_hook": (0.05, 0.65),  # fraction ≥100h
    "popularity": (200.0, 30000.0),  # peak players
}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _log_norm(x: float, lo: float, hi: float) -> float:
    x = max(float(x), 0.0)
    return _clamp((math.log1p(x) - math.log1p(lo)) / (math.log1p(hi) - math.log1p(lo)))


def _lin_norm(x: float, lo: float, hi: float) -> float:
    return _clamp((float(x) - lo) / (hi - lo))


@dataclass(frozen=True)
class GameFeatures:
    """Minimum feature set needed to score a game."""

    game: str
    scaled_median_playtime_h: float
    scaled_avg_playtime_h: float
    avg_last_2w_h: float
    pct_active_last_2w: float
    pct_100h_plus: float
    peak_players: float

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "GameFeatures":
        missing = [k for k in FEATURE_KEYS if k not in data or data[k] in (None, "")]
        if missing:
            raise ValueError(f"Missing required features: {', '.join(missing)}")
        return cls(
            game=str(data["game"]),
            scaled_median_playtime_h=float(data["scaled_median_playtime_h"]),
            scaled_avg_playtime_h=float(data["scaled_avg_playtime_h"]),
            avg_last_2w_h=float(data["avg_last_2w_h"]),
            pct_active_last_2w=float(data["pct_active_last_2w"]),
            pct_100h_plus=float(data["pct_100h_plus"]),
            peak_players=float(data["peak_players"]),
        )


Grade = str  # S/A/B/C/D/F


@dataclass(frozen=True)
class ScoreResult:
    game: str
    addictiveness: float
    grade: Grade
    estimated_avg_player_hours: float
    components: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def components_for(features: GameFeatures) -> dict[str, float]:
    depth_lo, depth_hi = ANCHORS["depth"]
    int_lo, int_hi = ANCHORS["intensity"]
    stick_lo, stick_hi = ANCHORS["stickiness"]
    hook_lo, hook_hi = ANCHORS["deep_hook"]
    pop_lo, pop_hi = ANCHORS["popularity"]
    return {
        "depth": _log_norm(features.scaled_median_playtime_h, depth_lo, depth_hi),
        "intensity": _log_norm(features.avg_last_2w_h, int_lo, int_hi),
        "stickiness": _lin_norm(features.pct_active_last_2w, stick_lo, stick_hi),
        "deep_hook": _lin_norm(features.pct_100h_plus, hook_lo, hook_hi),
        "popularity": _log_norm(max(features.peak_players, 1.0), pop_lo, pop_hi),
    }


def score_addictiveness(features: GameFeatures) -> tuple[float, dict[str, float]]:
    comps = components_for(features)
    score = 100.0 * sum(WEIGHTS[k] * comps[k] for k in WEIGHTS)
    return round(score, 1), {k: round(v, 4) for k, v in comps.items()}


def grade_from_score(score: float) -> Grade:
    if score >= 85:
        return "S"
    if score >= 75:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"


def estimate_avg_player_hours(
    features: GameFeatures,
    stickiness_component: float | None = None,
) -> float:
    med = features.scaled_median_playtime_h
    avg = features.scaled_avg_playtime_h
    capped_avg = min(avg, med * 2.2)
    base = 0.70 * med + 0.30 * capped_avg
    if stickiness_component is None:
        stickiness_component = components_for(features)["stickiness"]
    hours = base * (1.0 + 0.12 * stickiness_component)
    return round(hours, 1)


def score_game(features: GameFeatures | Mapping[str, Any]) -> ScoreResult:
    if not isinstance(features, GameFeatures):
        features = GameFeatures.from_mapping(features)
    addictiveness, comps = score_addictiveness(features)
    hours = estimate_avg_player_hours(features, stickiness_component=comps["stickiness"])
    return ScoreResult(
        game=features.game,
        addictiveness=addictiveness,
        grade=grade_from_score(addictiveness),
        estimated_avg_player_hours=hours,
        components=comps,
    )