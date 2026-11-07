#!/usr/bin/env python3
"""Build data/game_library.json (~1000 popular Steam games + factory overrides).

Steam rows come from the Hugging Face FronkonGames/steam-games-dataset
(SteamSpy-derived playtime + peak CCU). Factory titles override with the
high-confidence reviewer features from data/factory_game_features.json.

Usage:
  python3 scripts/build_library.py --parquet /path/to/games.parquet
  python3 scripts/build_library.py --parquet /path/to/games.parquet --limit 1000
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game_picker.model import score_game  # noqa: E402

EXCLUDE = re.compile(
    r"playtest|soundtrack|\bost\b|dedicated server|\bsdk\b| server\b|\bdemo\b|"
    r"bonus content|artbook|art book|digital comic|\btrailer\b|mod tools|"
    r"editor only|vtuber|cursor changer|crosshair|overlay|wallpaper engine|"
    r"\bhud\b|benchmark|server browser",
    re.I,
)

NON_GAME_GENRES = {
    "Utilities",
    "Design & Illustration",
    "Animation & Modeling",
    "Video Production",
    "Audio Production",
    "Photo Editing",
    "Web Publishing",
    "Software Training",
    "Game Development",
    "Accounting",
}


def _as_str_list(value, limit: int | None = None) -> list[str]:
    """Normalize parquet list / ndarray / None into a plain string list."""
    if value is None:
        return []
    try:
        # numpy arrays / pandas lists
        items = list(value)
    except TypeError:
        return []
    out: list[str] = []
    for item in items:
        s = str(item).strip()
        if s:
            out.append(s)
    if limit is not None:
        return out[:limit]
    return out

FACTORY_STEAM_NAMES = {
    "Factorio": "Factorio",
    "Mindustry": "Mindustry",
    "Shapez 1": "shapez",
    "Satisfactory": "Satisfactory",
    "Dyson Sphere Program": "Dyson Sphere Program",
    "Foundry": "Foundry",
    "Captain of Industry": "Captain of Industry",
    "Shapez 2": "shapez 2",
    "MineMogul": "Mine Mogul",
    "Alchemy Factory": "Alchemy Factory",
    "StarRupture": "StarRupture",
}


def owner_mid(s: object) -> float:
    if not isinstance(s, str) or not s.strip():
        return 0.0
    parts = re.findall(r"\d+", s.replace(",", ""))
    if len(parts) >= 2:
        return (float(parts[0]) + float(parts[1])) / 2.0
    if parts:
        return float(parts[0])
    return 0.0


def log_norm(x: float, lo: float, hi: float) -> float:
    x = max(float(x), 0.0)
    return max(
        0.0,
        min(1.0, (math.log1p(x) - math.log1p(lo)) / (math.log1p(hi) - math.log1p(lo))),
    )


def pct_100h_from_lognormal(mean_h: float, median_h: float) -> float:
    mean_h = max(float(mean_h), 1e-6)
    median_h = max(float(median_h), 1e-6)
    if mean_h < median_h:
        mean_h = median_h * 1.05
    ratio = mean_h / median_h
    sigma = math.sqrt(max(2.0 * math.log(ratio), 1e-8))
    mu = math.log(median_h)
    z = (math.log(100.0) - mu) / sigma
    phi = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return max(0.0, min(0.95, 1.0 - phi))


def proxy_pct_active(avg2_h: float, peak: float) -> float:
    """Approximate reviewer stickiness — SteamSpy has no % active field."""
    s_intensity = avg2_h / (avg2_h + 8.0)
    s_pop = log_norm(peak, 50, 200000)
    return max(0.02, min(0.92, 0.04 + 0.70 * s_intensity + 0.16 * s_pop))


def map_steam_row(r) -> dict:
    med_h = float(r["median_playtime_forever"] or 0) / 60.0
    avg_h = float(r["average_playtime_forever"] or 0) / 60.0
    avg2_h = float(r["average_playtime_2weeks"] or 0) / 60.0
    med2_h = float(r["median_playtime_2weeks"] or 0) / 60.0
    peak = float(r["peak_ccu"] or 0)

    features = {
        "game": str(r["name"]),
        "scaled_median_playtime_h": round(med_h, 3),
        "scaled_avg_playtime_h": round(avg_h, 3),
        "avg_last_2w_h": round(avg2_h, 3),
        "pct_active_last_2w": round(proxy_pct_active(avg2_h, peak), 4),
        "pct_100h_plus": round(pct_100h_from_lognormal(avg_h, med_h), 4),
        "peak_players": peak,
    }
    result = score_game(features)
    return {
        "app_id": str(r["appID"]),
        "header_image": r.get("header_image") or "",
        "release_date": r.get("release_date") or "",
        "genres": _as_str_list(r.get("genres")),
        "tags": _as_str_list(r.get("tags"), limit=12),
        "categories": _as_str_list(r.get("categories"), limit=20),
        "positive": int(r.get("positive") or 0),
        "negative": int(r.get("negative") or 0),
        "estimated_owners": r.get("estimated_owners") or "",
        "owners_mid": owner_mid(r.get("estimated_owners")),
        "steam_median_h": round(med_h, 3),
        "steam_avg_h": round(avg_h, 3),
        "steam_avg_2w_h": round(avg2_h, 3),
        "steam_median_2w_h": round(med2_h, 3),
        "peak_ccu": peak,
        "name": features["game"],
        "features": features,
        "feature_provenance": {
            "scaled_median_playtime_h": {
                "source": "steamspy_median_forever_minutes/60",
                "confidence": "medium",
                "note": "No age-scaling; raw SteamSpy median across owners.",
            },
            "scaled_avg_playtime_h": {
                "source": "steamspy_average_forever_minutes/60",
                "confidence": "medium",
            },
            "avg_last_2w_h": {
                "source": "steamspy_average_2weeks_minutes/60",
                "confidence": "medium" if avg2_h > 0 else "low",
            },
            "pct_active_last_2w": {
                "source": "proxy: 0.04+0.70*(avg2w/(avg2w+8))+0.16*log_norm(peak_ccu)",
                "confidence": "low",
                "note": "Factory sheets had reviewer % active; SteamSpy lacks it.",
            },
            "pct_100h_plus": {
                "source": "proxy: lognormal tail from mean & median",
                "confidence": "low",
            },
            "peak_players": {
                "source": "steam_dataset_peak_ccu",
                "confidence": "medium",
                "note": "Peak CCU from dataset snapshot, not necessarily all-time.",
            },
        },
        "data_source": "steam_dataset",
        "confidence": "mixed",
        "addictiveness": result.addictiveness,
        "grade": result.grade,
        "estimated_avg_player_hours": result.estimated_avg_player_hours,
        "components": result.components,
    }


def factory_entry(row: dict, steam_meta: dict | None = None) -> dict:
    features = {
        "game": row["game"],
        "scaled_median_playtime_h": row["scaled_median_playtime_h"],
        "scaled_avg_playtime_h": row["scaled_avg_playtime_h"],
        "avg_last_2w_h": row["avg_last_2w_h"],
        "pct_active_last_2w": row["pct_active_last_2w"],
        "pct_100h_plus": row["pct_100h_plus"],
        "peak_players": row["peak_players"],
    }
    result = score_game(features)
    entry = {
        "app_id": "",
        "header_image": "",
        "release_date": "",
        "genres": ["Strategy", "Simulation"],
        "tags": ["Factory", "Automation", "Base Building"],
        "categories": ["Single-player"],
        "positive": 0,
        "negative": 0,
        "estimated_owners": "",
        "owners_mid": 0,
        "steam_median_h": row.get("median_playtime_h"),
        "steam_avg_h": row.get("avg_playtime_h"),
        "steam_avg_2w_h": row.get("avg_last_2w_h"),
        "steam_median_2w_h": row.get("median_last_2w_h"),
        "peak_ccu": row["peak_players"],
        "name": row["game"],
        "features": features,
        "feature_provenance": {
            k: {"source": "factory_game_reviews_spreadsheet", "confidence": "high"}
            for k in features
            if k != "game"
        },
        "data_source": "factory_reviews",
        "confidence": "high",
        "addictiveness": result.addictiveness,
        "grade": result.grade,
        "estimated_avg_player_hours": result.estimated_avg_player_hours,
        "components": result.components,
    }
    if steam_meta:
        for key in (
            "app_id",
            "header_image",
            "release_date",
            "positive",
            "negative",
            "estimated_owners",
            "genres",
            "tags",
            "categories",
        ):
            if steam_meta.get(key):
                entry[key] = steam_meta[key]
        # Keep factory strategy/simulation signal even if Steam genres differ.
        merged = list(dict.fromkeys([*(entry.get("genres") or []), "Strategy", "Simulation"]))
        entry["genres"] = merged[:6]
    return entry


def build(parquet_path: Path, limit: int, factory_path: Path) -> dict:
    import pandas as pd

    df = pd.read_parquet(parquet_path)
    mask = (df["median_playtime_forever"].fillna(0) > 0) & df["name"].notna()
    cand = df.loc[mask].copy()
    cand = cand[~cand["name"].str.contains(EXCLUDE, na=False, regex=True)]

    def is_non_game(row) -> bool:
        genres = set(_as_str_list(row.get("genres")))
        if genres and genres <= NON_GAME_GENRES:
            return True
        if genres & NON_GAME_GENRES and not (genres - NON_GAME_GENRES - {"Free To Play", "Early Access"}):
            return True
        return False

    cand = cand[~cand.apply(is_non_game, axis=1)]
    cand["pop"] = (
        cand["peak_ccu"].fillna(0).astype(float)
        + cand["recommendations"].fillna(0).astype(float) * 0.05
        + cand["positive"].fillna(0).astype(float) * 0.002
    )
    cand = cand.sort_values("pop", ascending=False).drop_duplicates(subset=["name"], keep="first")

    library: list[dict] = []
    for _, r in cand.iterrows():
        entry = map_steam_row(r)
        if entry["features"]["scaled_median_playtime_h"] > 2000:
            continue
        library.append(entry)
        if len(library) >= limit:
            break

    by_exact = {g["name"].lower(): i for i, g in enumerate(library)}
    factory = json.loads(factory_path.read_text(encoding="utf-8"))

    for row in factory:
        steam_name = FACTORY_STEAM_NAMES.get(row["game"], row["game"])
        idx = by_exact.get(steam_name.lower())
        steam_meta = library[idx] if idx is not None else None
        entry = factory_entry(row, steam_meta)
        if idx is not None:
            library[idx] = entry
            by_exact[entry["name"].lower()] = idx
            # drop old steam key if renamed
            if steam_name.lower() != entry["name"].lower():
                by_exact.pop(steam_name.lower(), None)
        else:
            by_exact[entry["name"].lower()] = len(library)
            library.append(entry)

    # Keep all factory rows; trim steam filler to limit
    factory_rows = [g for g in library if g["data_source"] == "factory_reviews"]
    steam_rows = [g for g in library if g["data_source"] != "factory_reviews"]
    need = max(0, limit - len(factory_rows))
    library = factory_rows + steam_rows[:need]
    library.sort(key=lambda g: (-g["estimated_avg_player_hours"], g["name"].lower()))

    return {
        "generated_for": "game-picker",
        "count": len(library),
        "sources": {
            "steam": (
                "Hugging Face FronkonGames/steam-games-dataset "
                "(SteamSpy-derived playtime + peak CCU)"
            ),
            "factory": "Factory Game Reviews spreadsheet (high-confidence reviewer sample)",
        },
        "notes": [
            "pct_active_last_2w and pct_100h_plus are proxied for Steam rows (low confidence).",
            "Steam medians/averages are all-owner SteamSpy stats, typically lower than reviewer-only samples.",
            "Factory titles use spreadsheet features and confidence=high.",
        ],
        "games": library,
    }


def write_web_bundle(payload: dict, web_json: Path) -> None:
    """Slimmer JSON for the static UI (no provenance blobs)."""
    games = []
    for g in payload["games"]:
        games.append(
            {
                "name": g["name"],
                "app_id": g.get("app_id", ""),
                "header_image": g.get("header_image", ""),
                "genres": (g.get("genres") or [])[:6],
                "tags": (g.get("tags") or [])[:8],
                "categories": (g.get("categories") or [])[:12],
                "data_source": g["data_source"],
                "confidence": g["confidence"],
                "addictiveness": g["addictiveness"],
                "grade": g["grade"],
                "estimated_avg_player_hours": g["estimated_avg_player_hours"],
                "components": g["components"],
                "features": g["features"],
                "release_date": g.get("release_date", ""),
                "positive": g.get("positive", 0),
                "peak_ccu": g.get("peak_ccu", 0),
            }
        )
    web_json.parent.mkdir(parents=True, exist_ok=True)
    web_json.write_text(
        json.dumps(
            {
                "count": len(games),
                "sources": payload["sources"],
                "notes": payload["notes"],
                "games": games,
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def write_outputs(payload: dict, out_json: Path, out_csv: Path, web_json: Path | None = None) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    if web_json is not None:
        write_web_bundle(payload, web_json)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "name",
                "app_id",
                "data_source",
                "confidence",
                "addictiveness",
                "grade",
                "estimated_avg_player_hours",
                "scaled_median_playtime_h",
                "avg_last_2w_h",
                "peak_players",
            ],
        )
        writer.writeheader()
        for g in payload["games"]:
            writer.writerow(
                {
                    "name": g["name"],
                    "app_id": g.get("app_id", ""),
                    "data_source": g["data_source"],
                    "confidence": g["confidence"],
                    "addictiveness": g["addictiveness"],
                    "grade": g["grade"],
                    "estimated_avg_player_hours": g["estimated_avg_player_hours"],
                    "scaled_median_playtime_h": g["features"]["scaled_median_playtime_h"],
                    "avg_last_2w_h": g["features"]["avg_last_2w_h"],
                    "peak_players": g["features"]["peak_players"],
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True, help="Steam games parquet path")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--factory",
        type=Path,
        default=ROOT / "data" / "factory_game_features.json",
    )
    parser.add_argument("--out-json", type=Path, default=ROOT / "data" / "game_library.json")
    parser.add_argument("--out-csv", type=Path, default=ROOT / "data" / "game_library.csv")
    parser.add_argument("--web-json", type=Path, default=ROOT / "web" / "games.json")
    args = parser.parse_args()

    payload = build(args.parquet, args.limit, args.factory)
    write_outputs(payload, args.out_json, args.out_csv, args.web_json)
    n_factory = sum(1 for g in payload["games"] if g["data_source"] == "factory_reviews")
    print(f"Wrote {payload['count']} games ({n_factory} factory) → {args.out_json}")
    print(f"Web bundle → {args.web_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
