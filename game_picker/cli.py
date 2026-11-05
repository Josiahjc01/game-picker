"""CLI: score factory games for addictiveness and estimated playtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .model import FEATURE_KEYS, score_game
from .parse import load_features_csv, parse_workbook, write_features

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "factory_game_features.csv"
DEFAULT_XLSX = ROOT / "data" / "factory-game-reviews.xlsx"


def _print_table(results: list) -> None:
    header = f"{'Game':24} {'Score':>6} {'Grade':>5} {'Est. hours':>11}"
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda x: (-x.addictiveness, x.game)):
        print(
            f"{r.game:24} {r.addictiveness:6.1f} {r.grade:>5} {r.estimated_avg_player_hours:11.1f}"
        )


def cmd_score(args: argparse.Namespace) -> int:
    if args.features:
        games = load_features_csv(args.features)
    elif args.xlsx:
        games = parse_workbook(args.xlsx)
    else:
        if DEFAULT_FEATURES.exists():
            games = load_features_csv(DEFAULT_FEATURES)
        elif DEFAULT_XLSX.exists():
            games = parse_workbook(DEFAULT_XLSX)
        else:
            print(
                "No features CSV or xlsx found. Pass --features or --xlsx.",
                file=sys.stderr,
            )
            return 1

    results = [score_game(g) for g in games]

    if args.json:
        payload = [r.as_dict() for r in sorted(results, key=lambda x: -x.addictiveness)]
        print(json.dumps(payload, indent=2))
    else:
        _print_table(results)
        if args.verbose:
            print()
            for r in sorted(results, key=lambda x: -x.addictiveness):
                comps = ", ".join(f"{k}={v:.2f}" for k, v in r.components.items())
                print(f"  {r.game}: {comps}")
    return 0


def cmd_score_one(args: argparse.Namespace) -> int:
    if args.file:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    else:
        required = {
            "scaled_median_playtime_h": args.scaled_median,
            "scaled_avg_playtime_h": args.scaled_avg,
            "avg_last_2w_h": args.avg_last_2w,
            "pct_active_last_2w": args.pct_active,
            "pct_100h_plus": args.pct_100h,
            "peak_players": args.peak_players,
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            print(
                "score-one requires --file or all of: "
                "--scaled-median --scaled-avg --avg-last-2w "
                "--pct-active --pct-100h --peak-players "
                f"(missing: {', '.join(missing)})",
                file=sys.stderr,
            )
            return 2
        data = {"game": args.game, **required}
    result = score_game(data)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(
            f"{result.game}: addictiveness={result.addictiveness} "
            f"({result.grade}), est. avg player hours={result.estimated_avg_player_hours}"
        )
        if args.verbose:
            print("  components:", result.components)
    return 0


def cmd_build_features(args: argparse.Namespace) -> int:
    xlsx = Path(args.xlsx or DEFAULT_XLSX)
    games = parse_workbook(xlsx)
    out_csv = Path(args.out_csv or DEFAULT_FEATURES)
    out_json = Path(args.out_json) if args.out_json else out_csv.with_suffix(".json")
    write_features(games, out_csv, out_json)
    print(f"Wrote {len(games)} games → {out_csv} and {out_json}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="game-picker",
        description="Score factory games for addictiveness and estimate average-player playtime.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score", help="Score all games from features CSV or xlsx")
    score.add_argument("--features", type=Path, help="Path to features CSV")
    score.add_argument("--xlsx", type=Path, help="Path to reviews workbook")
    score.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    score.add_argument("-v", "--verbose", action="store_true", help="Show component scores")
    score.set_defaults(func=cmd_score)

    one = sub.add_parser(
        "score-one",
        help="Score a single game from flags or a JSON feature object",
    )
    one.add_argument("--file", type=Path, help="JSON file with required feature keys")
    one.add_argument("--game", default="Custom game")
    one.add_argument("--scaled-median", type=float, dest="scaled_median")
    one.add_argument("--scaled-avg", type=float, dest="scaled_avg")
    one.add_argument("--avg-last-2w", type=float, dest="avg_last_2w")
    one.add_argument("--pct-active", type=float, dest="pct_active")
    one.add_argument("--pct-100h", type=float, dest="pct_100h")
    one.add_argument("--peak-players", type=float, dest="peak_players")
    one.add_argument("--json", action="store_true")
    one.add_argument("-v", "--verbose", action="store_true")
    one.set_defaults(func=cmd_score_one)

    build = sub.add_parser("build-features", help="Rebuild features CSV/JSON from the xlsx")
    build.add_argument("--xlsx", type=Path, default=None)
    build.add_argument("--out-csv", type=Path, default=None)
    build.add_argument("--out-json", type=Path, default=None)
    build.set_defaults(func=cmd_build_features)

    keys = sub.add_parser("feature-keys", help="Print required keys for score-one input")
    keys.set_defaults(func=lambda _args: (print("\n".join(FEATURE_KEYS)), 0)[1])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())