#!/usr/bin/env python3
"""Rebuild data/factory_game_features.{csv,json} from the reviews workbook."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game_picker.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["build-features", *sys.argv[1:]]))