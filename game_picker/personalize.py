"""Fair personalization of baseline addictiveness + playtime estimates.

Profile → multipliers (documented, clamped) → personalized hours/score.
Calendar realism uses weekly free time as a soft/hard engagement horizon,
never inventing unlimited hours above a slight lift of the preference-adjusted
baseline.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from .model import grade_from_score

COMPLEX_GENRES = frozenset(
    {"Strategy", "Simulation", "RPG", "Massively Multiplayer", "Early Access"}
)
LIGHT_GENRES = frozenset({"Casual", "Adventure", "Racing", "Sports", "Indie"})

DEFAULT_GENRE_CHOICES = [
    "Action",
    "Adventure",
    "Casual",
    "Indie",
    "RPG",
    "Racing",
    "Simulation",
    "Sports",
    "Strategy",
    "Massively Multiplayer",
    "Free To Play",
]


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _norm_name(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class UserProfile:
    """In-depth preference profile used to recalibrate estimates."""

    liked_genres: list[str] = field(default_factory=list)
    disliked_genres: list[str] = field(default_factory=list)
    recent_genres: list[str] = field(default_factory=list)
    recent_games_text: str = ""
    # 0 = short sessions / snackable, 1 = long grind sessions
    pacing: float = 0.5
    # 0 = dabbler, 1 = completionist
    completionism: float = 0.5
    # 0 = solo-focused, 1 = multiplayer-focused
    multiplayer_bias: float = 0.35
    # 0 = simple systems, 1 = loves deep/complex games
    complexity_tolerance: float = 0.55
    # Hours available per week (calendar constraint)
    weekly_hours: float = 8.0

    def recent_game_names(self) -> list[str]:
        raw = self.recent_games_text.replace("\n", ",")
        parts = [p.strip() for p in re.split(r"[,;/|]+", raw) if p.strip()]
        return parts

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "UserProfile":
        if not data:
            return cls()
        return cls(
            liked_genres=[str(x) for x in data.get("liked_genres") or data.get("likedGenres") or []],
            disliked_genres=[
                str(x) for x in data.get("disliked_genres") or data.get("dislikedGenres") or []
            ],
            recent_genres=[
                str(x) for x in data.get("recent_genres") or data.get("recentGenres") or []
            ],
            recent_games_text=str(
                data.get("recent_games_text") or data.get("recentGamesText") or ""
            ),
            pacing=float(data.get("pacing", 0.5)),
            completionism=float(data.get("completionism", 0.5)),
            multiplayer_bias=float(
                data.get("multiplayer_bias", data.get("multiplayerBias", 0.35))
            ),
            complexity_tolerance=float(
                data.get("complexity_tolerance", data.get("complexityTolerance", 0.55))
            ),
            weekly_hours=max(0.5, float(data.get("weekly_hours", data.get("weeklyHours", 8.0)))),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PersonalizedResult:
    game: str
    baseline_hours: float
    baseline_addictiveness: float
    baseline_grade: str
    personalized_hours: float
    personalized_addictiveness: float
    personalized_grade: str
    hours_multiplier: float
    affinity: float
    pacing_fit: float
    complexity_fit: float
    multiplayer_fit: float
    calendar_weeks: float
    calendar_months: float
    horizon_weeks: float
    calendar_capped: bool
    reasons: list[str]
    confidence_note: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _genre_set(game: Mapping[str, Any]) -> set[str]:
    return {str(g) for g in (game.get("genres") or []) if g}


def _category_set(game: Mapping[str, Any]) -> set[str]:
    return {str(c) for c in (game.get("categories") or []) if c}


def _overlap_ratio(a: Sequence[str], b: set[str]) -> float:
    if not a:
        return 0.0
    hits = sum(1 for x in a if x in b)
    return hits / len(a)


def game_complexity(game: Mapping[str, Any], components: Mapping[str, float] | None = None) -> float:
    genres = _genre_set(game)
    if genres & COMPLEX_GENRES and not (genres <= LIGHT_GENRES):
        base = 0.75
    elif genres & LIGHT_GENRES and not (genres & COMPLEX_GENRES):
        base = 0.3
    elif not genres:
        base = 0.5
    else:
        base = 0.55
    depth = float((components or {}).get("depth") or 0.0)
    return _clamp(0.65 * base + 0.35 * depth, 0.0, 1.0)


def game_multiplayer_score(game: Mapping[str, Any]) -> float:
    cats = _category_set(game)
    genres = _genre_set(game)
    has_mp = any("Multi-player" in c or "Multiplayer" in c or c == "Co-op" for c in cats)
    has_mp = has_mp or "Massively Multiplayer" in genres
    has_sp = "Single-player" in cats
    if has_mp and not has_sp:
        return 1.0
    if has_mp and has_sp:
        return 0.55
    if has_sp:
        return 0.15
    return 0.4


def compute_affinity(profile: UserProfile, game: Mapping[str, Any]) -> tuple[float, list[str]]:
    """Return affinity in [-1, 1] and human reasons."""
    genres = _genre_set(game)
    reasons: list[str] = []
    liked = _overlap_ratio(profile.liked_genres, genres)
    disliked = _overlap_ratio(list(genres), set(profile.disliked_genres)) if genres else 0.0
    # If disliked list hits any game genre heavily
    if profile.disliked_genres and genres:
        disliked = len(genres & set(profile.disliked_genres)) / max(len(genres), 1)
    recent_g = _overlap_ratio(profile.recent_genres, genres)

    name_n = _norm_name(str(game.get("name") or game.get("game") or ""))
    recent_names = [_norm_name(x) for x in profile.recent_game_names()]
    exact_recent = any(name_n == r or (r and (r in name_n or name_n in r)) for r in recent_names)

    affinity = 0.0
    affinity += 0.50 * liked
    affinity -= 0.55 * disliked
    affinity += 0.25 * recent_g
    if exact_recent:
        affinity += 0.08  # familiarity
        reasons.append("Recently played / in rotation (small familiarity boost)")
    if liked > 0:
        reasons.append(f"Liked-genre overlap {liked:.0%}")
    if disliked > 0:
        reasons.append(f"Disliked-genre overlap {disliked:.0%} (penalty)")
    if recent_g > 0 and not exact_recent:
        reasons.append(f"Matches recent genre mix ({recent_g:.0%})")
    if not genres:
        affinity *= 0.85
        reasons.append("Thin genre metadata — muted affinity signal")

    affinity = _clamp(affinity, -1.0, 1.0)
    if not reasons:
        reasons.append("Neutral genre fit (no strong likes/dislikes matched)")
    return affinity, reasons


def personalize_game(
    game: Mapping[str, Any],
    profile: UserProfile | Mapping[str, Any] | None = None,
) -> PersonalizedResult:
    """Adjust baseline library scores using a user profile."""
    if not isinstance(profile, UserProfile):
        profile = UserProfile.from_mapping(profile)

    name = str(game.get("name") or game.get("game") or "Unknown")
    baseline_hours = float(game.get("estimated_avg_player_hours") or 0.0)
    baseline_add = float(game.get("addictiveness") or 0.0)
    baseline_grade = str(game.get("grade") or grade_from_score(baseline_add))
    components = game.get("components") or {}

    affinity, reasons = compute_affinity(profile, game)
    complexity = game_complexity(game, components)
    mp = game_multiplayer_score(game)
    depth = float(components.get("depth") or 0.5)

    pacing_fit = 1.0 - abs(profile.pacing - depth)
    complexity_fit = 1.0 - abs(profile.complexity_tolerance - complexity)
    mp_fit = 1.0 - abs(profile.multiplayer_bias - mp)

    # Multiplier centered at 1.0 — clamped so similar profiles stay consistent.
    hours_mult = (
        1.0
        + 0.35 * affinity
        + 0.15 * (pacing_fit - 0.5) * 2.0
        + 0.12 * (complexity_fit - 0.5) * 2.0
        + 0.10 * (mp_fit - 0.5) * 2.0
        + 0.10 * (profile.completionism - 0.5) * 2.0
    )
    hours_mult = _clamp(hours_mult, 0.50, 1.55)
    h_pref = baseline_hours * hours_mult

    # Calendar horizon: interest window grows with baseline hook + affinity + completionism.
    affinity_01 = (affinity + 1.0) / 2.0
    horizon = 6.0 + 10.0 * (baseline_add / 100.0) * (0.45 + 0.55 * affinity_01)
    horizon *= 0.9 + 0.4 * profile.completionism
    horizon = _clamp(horizon, 4.0, 26.0)

    calendar_cap = profile.weekly_hours * horizon
    calendar_capped = h_pref > calendar_cap + 1e-6
    # Never invent hours far above preference-adjusted baseline.
    h_you = min(h_pref, calendar_cap, baseline_hours * hours_mult * 1.0)
    h_you = min(h_you, h_pref)  # explicit
    h_you = round(max(0.5, h_you), 1)

    if calendar_capped:
        reasons.append(
            f"Weekly free time caps engagement at ~{profile.weekly_hours:g}h × {horizon:.0f}w horizon"
        )
    if hours_mult >= 1.08:
        reasons.append(f"Preference uplift ×{hours_mult:.2f}")
    elif hours_mult <= 0.92:
        reasons.append(f"Preference downshift ×{hours_mult:.2f}")

    # Addictiveness shift: affinity-led, modest.
    a_you = baseline_add + 16.0 * affinity + 5.0 * (complexity_fit - 0.5) * 2.0
    a_you += 4.0 * (pacing_fit - 0.5) * 2.0
    a_you = round(_clamp(a_you, 0.0, 100.0), 1)
    grade = grade_from_score(a_you)

    weeks = h_you / max(profile.weekly_hours, 0.5)
    months = weeks / 4.345

    conf = str(game.get("confidence") or "mixed")
    if conf == "high":
        note = "High-confidence baseline (factory sample), then fair preference multipliers."
    else:
        note = (
            "Mixed-confidence Steam baseline (some proxied fields); "
            "personalization is deterministic but inherits that uncertainty."
        )
    if not _genre_set(game):
        note += " Thin genre tags on this title — affinity is muted."

    return PersonalizedResult(
        game=name,
        baseline_hours=round(baseline_hours, 1),
        baseline_addictiveness=round(baseline_add, 1),
        baseline_grade=baseline_grade,
        personalized_hours=h_you,
        personalized_addictiveness=a_you,
        personalized_grade=grade,
        hours_multiplier=round(hours_mult, 3),
        affinity=round(affinity, 3),
        pacing_fit=round(pacing_fit, 3),
        complexity_fit=round(complexity_fit, 3),
        multiplayer_fit=round(mp_fit, 3),
        calendar_weeks=round(weeks, 1),
        calendar_months=round(months, 1),
        horizon_weeks=round(horizon, 1),
        calendar_capped=calendar_capped,
        reasons=reasons[:6],
        confidence_note=note,
    )
