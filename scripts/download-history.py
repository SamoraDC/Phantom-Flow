#!/usr/bin/env python3
"""Download historical market data from Binance for backtesting."""

import argparse
import gzip
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE_URL = "https://data.binance.vision/data/spot/daily/klines"


def download_klines(
    symbol: str,
    interval: str,
    start_date: datetime,
    end_date: datetime,
    output_dir: Path,
) -> None:
    """Download kline data for a date range."""
    output_dir.mkdir(parents=True, exist_ok=True)

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        filename = f"{symbol}-{interval}-{date_str}.csv"
        url = f"{BASE_URL}/{symbol}/{interval}/{filename}.zip"

        output_path = output_dir / filename

        if output_path.exists():
            print(f"Skipping {filename} (already exists)")
            current_date += timedelta(days=1)
            continue

        print(f"Downloading {filename}...")

        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # Save as CSV (unzip if needed)
                import zipfile
                import io

                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    z.extractall(output_dir)
                print(f"  Saved to {output_path}")
            elif response.status_code == 404:
                print(f"  Not available (possibly weekend or future date)")
            else:
                print(f"  Failed with status {response.status_code}")
        except Exception as e:
            print(f"  Error: {e}")

        current_date += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(description="Download Binance historical data")
    parser.add_argument(
        "--symbol", "-s",
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)"
    )
    parser.add_argument(
        "--interval", "-i",
        default="1m",
        choices=["1m", "5m", "15m", "1h", "4h", "1d"],
        help="Kline interval (default: 1m)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=30,
        help="Number of days to download (default: 30)"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/history",
        help="Output directory (default: data/history)"
    )

    args = parser.parse_args()

    end_date = datetime.now() - timedelta(days=1)  # Yesterday
    start_date = end_date - timedelta(days=args.days)

    print(f"Downloading {args.symbol} {args.interval} data")
    print(f"  From: {start_date.strftime('%Y-%m-%d')}")
    print(f"  To: {end_date.strftime('%Y-%m-%d')}")
    print(f"  Output: {args.output}")
    print()

    download_klines(
        symbol=args.symbol,
        interval=args.interval,
        start_date=start_date,
        end_date=end_date,
        output_dir=Path(args.output),
    )

    print("\nDone!")


if __name__ == "__main__":
    main()
