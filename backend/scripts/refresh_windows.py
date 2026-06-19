#!/usr/bin/env python3
"""Refresh analytical telemetry windows."""

from __future__ import annotations

import argparse

from dpf_backend.analyzer.windows import WINDOW_BUCKET_SECONDS, WindowRefresher
from dpf_backend.config import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bucket-seconds",
        type=int,
        action="append",
        choices=WINDOW_BUCKET_SECONDS,
        help="Bucket size to refresh. Can be passed more than once.",
    )
    args = parser.parse_args()

    buckets = tuple(args.bucket_seconds or WINDOW_BUCKET_SECONDS)
    settings = load_settings()
    with WindowRefresher(settings.database_url) as refresher:
        for bucket in buckets:
            inserted = refresher.refresh_bucket(bucket)
            print(f"Refreshed {bucket}s windows: {inserted} row(s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
