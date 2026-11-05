"""Parse the factory-game reviews workbook into per-game feature rows."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

# Sheet tab → (display name, Graphs-tab lookup key)
SHEET_TO_GAME: dict[str, tuple[str, str]] = {
    "Fa": ("Factorio", "Factorio"),
    "Mind": ("Mindustry", "Mindustry"),
    "S1": ("Shapez 1", "Shapez 1"),
    "Sa": ("Satisfactory", "Satisfactory"),
    "Dy": ("Dyson Sphere Program", "Dyson Sphere"),
    "Fo": ("Foundry", "Foundry"),
    "Ca": ("Captain of Industry", "Captain of Industry"),
    "S2": ("Shapez 2", "Shapez 2"),
    "Mine": ("MineMogul", "MineMogul"),
    "Al": ("Alchemy Factory", "Alchemy Factory"),
    "St": ("StarRupture", "StarRupture"),
}

FEATURE_FIELDNAMES = [
    "game",
    "sheet",
    "n_reviews",
    "days_since_release",
    "age_scale_diff",
    "avg_playtime_h",
    "median_playtime_h",
    "avg_at_review_h",
    "median_at_review_h",
    "avg_last_2w_h",
    "median_last_2w_h",
    "highest_playtime_h",
    "scaled_avg_playtime_h",
    "scaled_median_playtime_h",
    "scaled_avg_last_2w_h",
    "peak_players",
    "pct_active_last_2w",
    "pct_100h_plus",
    "pct_500h_plus",
    "p75_playtime_h",
    "p90_playtime_h",
]


def _read_metric_block(ws, start_row: int, end_row: int) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for r in range(start_row, end_row + 1):
        label = ws.cell(r, 4).value
        if label in ("Average", "Median", "Mode", "Highest"):
            out[str(label)] = {
                "playtime": float(ws.cell(r, 5).value or 0),
                "at_review": float(ws.cell(r, 6).value or 0),
                "last_2w": float(ws.cell(r, 7).value or 0),
            }
    return out


def _graphs_lookups(wb) -> tuple[dict[str, float], dict[str, float]]:
    """Peak players + recent playtime live on the Graphs sheet (messy layout)."""
    graphs = wb["Graphs"]
    recent: dict[str, float] = {}
    peak: dict[str, float] = {}
    for r in range(25, 36):
        g = graphs.cell(r, 1).value
        v = graphs.cell(r, 2).value
        if isinstance(g, str) and isinstance(v, (int, float)):
            recent[g] = float(v)
        g2 = graphs.cell(r, 9).value
        v2 = graphs.cell(r, 10).value
        if isinstance(g2, str) and isinstance(v2, (int, float)):
            peak[g2] = float(v2)
    return recent, peak


def parse_workbook(xlsx_path: str | Path) -> list[dict[str, Any]]:
    """Extract one feature dict per game from the reviews xlsx."""
    wb = load_workbook(xlsx_path, data_only=True)
    _recent, peak = _graphs_lookups(wb)
    games: list[dict[str, Any]] = []

    for sheet, (name, graphs_key) in SHEET_TO_GAME.items():
        ws = wb[sheet]
        raw = _read_metric_block(ws, 1, 8)
        scaled = _read_metric_block(ws, 11, 20)
        days = float(ws.cell(8, 4).value)
        age_diff = float(ws.cell(8, 6).value)

        playtimes: list[float] = []
        last2: list[float] = []
        for r in range(2, ws.max_row + 1):
            p = ws.cell(r, 1).value
            l = ws.cell(r, 3).value
            if not isinstance(p, (int, float)):
                continue
            if not isinstance(l, (int, float)):
                continue
            playtimes.append(float(p))
            last2.append(float(l))

        n = len(playtimes)
        if n == 0:
            raise ValueError(f"No reviewer samples found on sheet {sheet!r}")

        active = sum(1 for x in last2 if x > 0)
        sorted_pt = sorted(playtimes)
        games.append(
            {
                "game": name,
                "sheet": sheet,
                "n_reviews": n,
                "days_since_release": round(days, 1),
                "age_scale_diff": round(age_diff, 6),
                "avg_playtime_h": round(raw["Average"]["playtime"], 3),
                "median_playtime_h": round(raw["Median"]["playtime"], 3),
                "avg_at_review_h": round(raw["Average"]["at_review"], 3),
                "median_at_review_h": round(raw["Median"]["at_review"], 3),
                "avg_last_2w_h": round(raw["Average"]["last_2w"], 3),
                "median_last_2w_h": round(raw["Median"]["last_2w"], 3),
                "highest_playtime_h": round(raw["Highest"]["playtime"], 3),
                "scaled_avg_playtime_h": round(scaled["Average"]["playtime"], 3),
                "scaled_median_playtime_h": round(scaled["Median"]["playtime"], 3),
                "scaled_avg_last_2w_h": round(scaled["Average"]["last_2w"], 3),
                "peak_players": peak.get(graphs_key),
                "pct_active_last_2w": round(active / n, 4),
                "pct_100h_plus": round(sum(1 for x in playtimes if x >= 100) / n, 4),
                "pct_500h_plus": round(sum(1 for x in playtimes if x >= 500) / n, 4),
                "p75_playtime_h": round(sorted_pt[int(0.75 * (n - 1))], 3),
                "p90_playtime_h": round(sorted_pt[int(0.90 * (n - 1))], 3),
            }
        )

    games.sort(key=lambda g: g["game"])
    return games


def write_features(
    games: list[dict[str, Any]],
    csv_path: str | Path,
    json_path: str | Path | None = None,
) -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_FIELDNAMES)
        writer.writeheader()
        for row in games:
            writer.writerow({k: row.get(k) for k in FEATURE_FIELDNAMES})

    if json_path is not None:
        json_path = Path(json_path)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(games, indent=2) + "\n", encoding="utf-8")


def load_features_csv(csv_path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            parsed: dict[str, Any] = {"game": row["game"], "sheet": row.get("sheet", "")}
            for key, value in row.items():
                if key in ("game", "sheet") or value in (None, ""):
                    continue
                if key == "n_reviews":
                    parsed[key] = int(float(value))
                else:
                    parsed[key] = float(value)
            rows.append(parsed)
    return rows