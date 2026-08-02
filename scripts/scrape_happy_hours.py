#!/usr/bin/env python3
"""Backward-compat entry point for the scrape pipeline.

Implementation lives in scripts/scraper/ (Phase 5, issue #30):
  fetch.py   — page acquisition + contamination guard
  extract.py — pydantic schema, prompt, DeepSeek call, content-hash cache
  merge.py   — venue_to_site_record (carry-through)
  cli.py     — orchestration (run) + argparse

Usage (unchanged):
  python scripts/scrape_happy_hours.py [--dry-run] [--venue <id> ...] [--force]
"""

from scraper.cli import main

if __name__ == "__main__":
    main()
