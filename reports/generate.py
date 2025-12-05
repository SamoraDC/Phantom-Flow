#!/usr/bin/env python3
"""Report generator for QuantumFlow HFT Paper Trading.

Generates performance charts and updates the README with latest metrics.
Designed to run daily via GitHub Actions.
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader


# Configuration
DB_PATH = os.environ.get("DATABASE_URL", "sqlite:///data/trades.db").replace("sqlite:///", "")
OUTPUT_DIR = Path(__file__).parent / "assets"
TEMPLATE_DIR = Path(__file__).parent / "templates"
README_PATH = Path(__file__).parent.parent / "README.md"


def load_trades(db_path: str) -> pd.DataFrame:
    """Load trades from SQLite database."""
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        return pd.DataFrame()

    conn = sqlite3.connect(db_path)
    query = """
        SELECT
            id, order_id, symbol, side, price, quantity,
            fee, pnl, timestamp
        FROM trades
        ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["price"] = pd.to_numeric(df["price"])
        df["quantity"] = pd.to_numeric(df["quantity"])
        df["fee"] = pd.to_numeric(df["fee"])
        df["pnl"] = pd.to_numeric(df["pnl"].fillna(0))

    return df


def calculate_metrics(trades: pd.DataFrame, initial_balance: float = 10000.0) -> dict[str, Any]:
    """Calculate performance metrics from trades."""
    if trades.empty:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "total_pnl_pct": 0.0,
            "total_fees": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "avg_trade_pnl": 0.0,
            "trading_days": 0,
            "trades_per_day": 0.0,
            "equity_curve": [],
            "drawdown_curve": [],
        }

    total_trades = len(trades)
    winning = trades[trades["pnl"] > 0]
    losing = trades[trades["pnl"] < 0]

    total_pnl = trades["pnl"].sum()
    total_fees = trades["fee"].sum()

    # Equity curve
    trades["cumulative_pnl"] = trades["pnl"].cumsum()
    trades["equity"] = initial_balance + trades["cumulative_pnl"]

    # Drawdown calculation
    trades["peak"] = trades["equity"].cummax()
    trades["drawdown"] = trades["equity"] - trades["peak"]
    trades["drawdown_pct"] = trades["drawdown"] / trades["peak"] * 100

    max_drawdown = trades["drawdown"].min()
    max_drawdown_pct = trades["drawdown_pct"].min()

    # Sharpe ratio (daily returns)
    daily_pnl = trades.groupby(trades["timestamp"].dt.date)["pnl"].sum()
    if len(daily_pnl) > 1:
        sharpe = (daily_pnl.mean() / daily_pnl.std()) * np.sqrt(252) if daily_pnl.std() > 0 else 0
    else:
        sharpe = 0

    # Profit factor
    gross_profit = winning["pnl"].sum() if not winning.empty else 0
    gross_loss = abs(losing["pnl"].sum()) if not losing.empty else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    # Trading days
    trading_days = trades["timestamp"].dt.date.nunique()

    return {
        "total_trades": total_trades,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": len(winning) / total_trades * 100 if total_trades > 0 else 0,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl / initial_balance * 100,
        "total_fees": total_fees,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "profit_factor": profit_factor,
        "avg_win": winning["pnl"].mean() if not winning.empty else 0,
        "avg_loss": losing["pnl"].mean() if not losing.empty else 0,
        "largest_win": winning["pnl"].max() if not winning.empty else 0,
        "largest_loss": losing["pnl"].min() if not losing.empty else 0,
        "avg_trade_pnl": trades["pnl"].mean(),
        "trading_days": trading_days,
        "trades_per_day": total_trades / trading_days if trading_days > 0 else 0,
        "equity_curve": trades[["timestamp", "equity"]].to_dict("records"),
        "drawdown_curve": trades[["timestamp", "drawdown_pct"]].to_dict("records"),
    }


def generate_equity_curve(trades: pd.DataFrame, output_path: Path, initial_balance: float = 10000.0) -> None:
    """Generate equity curve chart."""
    if trades.empty:
        return

    trades["cumulative_pnl"] = trades["pnl"].cumsum()
    trades["equity"] = initial_balance + trades["cumulative_pnl"]

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(trades["timestamp"], trades["equity"], color="#2ecc71", linewidth=2)
    ax.axhline(y=initial_balance, color="#7f8c8d", linestyle="--", alpha=0.7, label="Initial Balance")

    # Fill between for gains/losses
    ax.fill_between(
        trades["timestamp"],
        initial_balance,
        trades["equity"],
        where=(trades["equity"] >= initial_balance),
        color="#2ecc71",
        alpha=0.3,
    )
    ax.fill_between(
        trades["timestamp"],
        initial_balance,
        trades["equity"],
        where=(trades["equity"] < initial_balance),
        color="#e74c3c",
        alpha=0.3,
    )

    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Equity ($)", fontsize=12)
    ax.set_title("Equity Curve", fontsize=14, fontweight="bold")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

    print(f"Generated: {output_path}")


def generate_drawdown_chart(trades: pd.DataFrame, output_path: Path, initial_balance: float = 10000.0) -> None:
    """Generate drawdown chart."""
    if trades.empty:
        return

    trades["cumulative_pnl"] = trades["pnl"].cumsum()
    trades["equity"] = initial_balance + trades["cumulative_pnl"]
    trades["peak"] = trades["equity"].cummax()
    trades["drawdown_pct"] = (trades["equity"] - trades["peak"]) / trades["peak"] * 100

    fig, ax = plt.subplots(figsize=(12, 4))

    ax.fill_between(
        trades["timestamp"],
        0,
        trades["drawdown_pct"],
        color="#e74c3c",
        alpha=0.7,
    )

    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Drawdown (%)", fontsize=12)
    ax.set_title("Drawdown", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

    print(f"Generated: {output_path}")


def generate_pnl_distribution(trades: pd.DataFrame, output_path: Path) -> None:
    """Generate P&L distribution histogram."""
    if trades.empty:
        return

    pnl_values = trades["pnl"].dropna()

    fig, ax = plt.subplots(figsize=(10, 6))

    # Color bins by positive/negative
    n, bins, patches = ax.hist(pnl_values, bins=50, edgecolor="black", alpha=0.7)

    for i, patch in enumerate(patches):
        if bins[i] >= 0:
            patch.set_facecolor("#2ecc71")
        else:
            patch.set_facecolor("#e74c3c")

    ax.axvline(x=0, color="black", linestyle="-", linewidth=2)
    ax.axvline(x=pnl_values.mean(), color="#3498db", linestyle="--", linewidth=2, label=f"Mean: ${pnl_values.mean():.2f}")

    ax.set_xlabel("P&L ($)", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.set_title("Trade P&L Distribution", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

    print(f"Generated: {output_path}")


def generate_hourly_heatmap(trades: pd.DataFrame, output_path: Path) -> None:
    """Generate P&L heatmap by hour and day of week."""
    if trades.empty:
        return

    trades["hour"] = trades["timestamp"].dt.hour
    trades["dayofweek"] = trades["timestamp"].dt.dayofweek

    pivot = trades.pivot_table(
        values="pnl",
        index="hour",
        columns="dayofweek",
        aggfunc="sum",
        fill_value=0,
    )

    # Ensure all hours and days are present
    all_hours = range(24)
    all_days = range(7)
    pivot = pivot.reindex(index=all_hours, columns=all_days, fill_value=0)

    fig, ax = plt.subplots(figsize=(10, 8))

    cmap = plt.cm.RdYlGn
    im = ax.imshow(pivot.values, cmap=cmap, aspect="auto")

    ax.set_xticks(range(7))
    ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_yticks(range(24))
    ax.set_yticklabels([f"{h:02d}:00" for h in range(24)])

    ax.set_xlabel("Day of Week", fontsize=12)
    ax.set_ylabel("Hour (UTC)", fontsize=12)
    ax.set_title("P&L Heatmap by Time", fontsize=14, fontweight="bold")

    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("P&L ($)", fontsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

    print(f"Generated: {output_path}")


def update_readme(metrics: dict[str, Any], readme_path: Path) -> None:
    """Update README with latest metrics."""
    # Load template
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    try:
        template = env.get_template("metrics_section.md.j2")
        metrics_section = template.render(
            metrics=metrics,
            updated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
    except Exception as e:
        print(f"Template error: {e}")
        # Fallback to simple format
        metrics_section = f"""
## Live Performance

*Last updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}*

| Metric | Value |
|--------|-------|
| Total Trades | {metrics['total_trades']} |
| Win Rate | {metrics['win_rate']:.1f}% |
| Total P&L | ${metrics['total_pnl']:.2f} ({metrics['total_pnl_pct']:.2f}%) |
| Sharpe Ratio | {metrics['sharpe_ratio']:.2f} |
| Max Drawdown | {metrics['max_drawdown_pct']:.2f}% |
| Profit Factor | {metrics['profit_factor']:.2f} |

### Equity Curve
![Equity Curve](reports/assets/equity_curve.png)

### Drawdown
![Drawdown](reports/assets/drawdown.png)

### Trade Distribution
![P&L Distribution](reports/assets/pnl_distribution.png)

### P&L Heatmap
![Hourly Heatmap](reports/assets/hourly_heatmap.png)
"""

    # Read current README
    if readme_path.exists():
        readme_content = readme_path.read_text()

        # Replace between markers
        start_marker = "<!-- METRICS_START -->"
        end_marker = "<!-- METRICS_END -->"

        if start_marker in readme_content and end_marker in readme_content:
            before = readme_content.split(start_marker)[0]
            after = readme_content.split(end_marker)[1]
            readme_content = f"{before}{start_marker}\n{metrics_section}\n{end_marker}{after}"
        else:
            # Append if markers don't exist
            readme_content += f"\n{start_marker}\n{metrics_section}\n{end_marker}\n"

        readme_path.write_text(readme_content)
        print(f"Updated: {readme_path}")


def main() -> int:
    """Main entry point."""
    print("QuantumFlow Report Generator")
    print("=" * 40)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load trades
    print(f"Loading trades from: {DB_PATH}")
    trades = load_trades(DB_PATH)

    if trades.empty:
        print("No trades found. Generating placeholder report.")

    # Calculate metrics
    metrics = calculate_metrics(trades)
    print(f"Total trades: {metrics['total_trades']}")
    print(f"Total P&L: ${metrics['total_pnl']:.2f}")

    # Generate charts
    if not trades.empty:
        generate_equity_curve(trades, OUTPUT_DIR / "equity_curve.png")
        generate_drawdown_chart(trades, OUTPUT_DIR / "drawdown.png")
        generate_pnl_distribution(trades, OUTPUT_DIR / "pnl_distribution.png")
        generate_hourly_heatmap(trades, OUTPUT_DIR / "hourly_heatmap.png")

    # Update README
    update_readme(metrics, README_PATH)

    print("\nReport generation complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
