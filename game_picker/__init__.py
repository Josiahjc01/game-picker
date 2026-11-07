"""Factory-game addictiveness scoring and playtime estimation."""

from .model import (
    FEATURE_KEYS,
    GameFeatures,
    Grade,
    ScoreResult,
    estimate_avg_player_hours,
    grade_from_score,
    score_addictiveness,
    score_game,
)
from .personalize import PersonalizedResult, UserProfile, personalize_game

__all__ = [
    "FEATURE_KEYS",
    "GameFeatures",
    "Grade",
    "ScoreResult",
    "PersonalizedResult",
    "UserProfile",
    "estimate_avg_player_hours",
    "grade_from_score",
    "personalize_game",
    "score_addictiveness",
    "score_game",
]

__version__ = "0.1.0"