"""
Stock Data Intelligence Dashboard - FastAPI Backend
Endpoints: /companies, /data/{symbol}, /summary/{symbol}, /compare
"""

import sqlite3
import os
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
from data_collector import run_data_pipeline, DB_PATH

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.path.exists(DB_PATH):
        print("📦 First run - fetching stock data (this may take ~30s)...")
        run_data_pipeline()
    else:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM stock_data").fetchone()[0]
        conn.close()
        if count == 0:
            print("📦 DB empty - fetching stock data...")
            run_data_pipeline()
        else:
            print(f"✅ DB ready with {count} rows")
    yield

app = FastAPI(
    title="📈 Stock Data Intelligence Dashboard",
    description="""
A mini financial data platform for Indian stock market data.

## Features
- Real-time stock data from NSE (via yfinance)
- Calculated metrics: Daily Return, 7-day MA, Volatility Score
- Compare two stocks side by side
- 52-week High/Low summary

## Custom Metric: Volatility Score
Normalized score (0-100) based on rolling std deviation relative to mean.
Higher = more volatile stock.
    """,
    version="1.0.0",
    contact={"name": "Stock Dashboard", "email": "support@jarnox.com"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    return sqlite3.connect(DB_PATH)


def row_to_dict(cursor, row):
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


# ─── Endpoint 1: GET /companies ───────────────────────────────────────────────
@app.get("/companies", summary="List all available companies")
def get_companies():
    """
    Returns all available companies with their sector info
    and latest stock stats (today's price, daily return).
    """
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT c.symbol, c.name, c.sector,
               s.close AS latest_close,
               s.daily_return AS latest_return,
               s.volatility_score
        FROM companies c
        JOIN stock_data s ON c.symbol = s.symbol
        WHERE s.date = (
            SELECT MAX(date) FROM stock_data WHERE symbol = c.symbol
        )
        ORDER BY c.name
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No company data found. Run data pipeline first.")

    return {
        "count": len(rows),
        "companies": [
            {
                "symbol": r[0],
                "name": r[1],
                "sector": r[2],
                "latest_close": round(r[3], 2),
                "daily_return_pct": round(r[4], 3),
                "volatility_score": round(r[5], 1),
            }
            for r in rows
        ]
    }


# ─── Endpoint 2: GET /data/{symbol} ───────────────────────────────────────────
@app.get("/data/{symbol}", summary="Get last 30 days of stock data")
def get_stock_data(
    symbol: str,
    days: int = Query(default=30, ge=7, le=365, description="Number of days (7–365)")
):
    """
    Returns last N days of stock data for the given symbol.
    Includes: OHLCV + Daily Return + 7-day MA + Volatility Score.
    Default: last 30 days.
    """
    symbol = symbol.upper()
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM companies WHERE symbol=?", (symbol,))
    if c.fetchone()[0] == 0:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found.")

    c.execute("""
        SELECT date, open, high, low, close, volume,
               daily_return, ma_7, volatility_score
        FROM stock_data
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT ?
    """, (symbol, days))
    rows = c.fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    data = [
        {
            "date": r[0], "open": r[1], "high": r[2], "low": r[3],
            "close": r[4], "volume": r[5],
            "daily_return_pct": r[6], "ma_7": r[7], "volatility_score": r[8]
        }
        for r in reversed(rows)  # chronological order
    ]

    return {
        "symbol": symbol,
        "days_returned": len(data),
        "data": data
    }


# ─── Endpoint 3: GET /summary/{symbol} ────────────────────────────────────────
@app.get("/summary/{symbol}", summary="52-week summary for a stock")
def get_summary(symbol: str):
    """
    Returns 52-week High, Low, Average Close, Total Volume,
    Best Day, Worst Day, and current Volatility Score.
    """
    symbol = symbol.upper()
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT
            MAX(high) as week52_high,
            MIN(low)  as week52_low,
            AVG(close) as avg_close,
            SUM(volume) as total_volume,
            MAX(daily_return) as best_return,
            MIN(daily_return) as worst_return,
            AVG(volatility_score) as avg_volatility
        FROM stock_data
        WHERE symbol = ?
        AND date >= date('now', '-365 days')
    """, (symbol,))
    row = c.fetchone()

    # Best/worst day details
    c.execute("""
        SELECT date, daily_return, close FROM stock_data
        WHERE symbol=? ORDER BY daily_return DESC LIMIT 1
    """, (symbol,))
    best_day = c.fetchone()

    c.execute("""
        SELECT date, daily_return, close FROM stock_data
        WHERE symbol=? ORDER BY daily_return ASC LIMIT 1
    """, (symbol,))
    worst_day = c.fetchone()

    # Latest close
    c.execute("""
        SELECT close, date FROM stock_data
        WHERE symbol=? ORDER BY date DESC LIMIT 1
    """, (symbol,))
    latest = c.fetchone()

    conn.close()

    if not row or row[0] is None:
        raise HTTPException(status_code=404, detail=f"No data for '{symbol}'")

    current_price = latest[0] if latest else 0
    week52_high = round(row[0], 2)
    week52_low = round(row[1], 2)
    price_range_pct = round((week52_high - week52_low) / week52_low * 100, 2) if week52_low else 0

    return {
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "as_of": latest[1] if latest else "N/A",
        "52_week": {
            "high": week52_high,
            "low": week52_low,
            "avg_close": round(row[2], 2),
            "price_range_pct": price_range_pct,
        },
        "volume": {"total_52w": int(row[3]) if row[3] else 0},
        "performance": {
            "best_day": {"date": best_day[0], "return_pct": round(best_day[1], 3), "close": round(best_day[2], 2)} if best_day else {},
            "worst_day": {"date": worst_day[0], "return_pct": round(worst_day[1], 3), "close": round(worst_day[2], 2)} if worst_day else {},
        },
        "custom_metric": {
            "avg_volatility_score": round(row[6], 2) if row[6] else 0,
            "interpretation": (
                "Low volatility (stable)" if (row[6] or 0) < 30 else
                "Medium volatility" if (row[6] or 0) < 60 else
                "High volatility (risky)"
            )
        }
    }


# ─── Endpoint 4 (Bonus): GET /compare ─────────────────────────────────────────
@app.get("/compare", summary="Compare two stocks' performance")
def compare_stocks(
    symbol1: str = Query(..., description="First stock symbol (e.g., INFY)"),
    symbol2: str = Query(..., description="Second stock symbol (e.g., TCS)"),
    days: int = Query(default=30, ge=7, le=365)
):
    """
    Compare two stocks side-by-side.
    Returns normalized price (base 100), daily returns, and correlation coefficient.
    """
    s1, s2 = symbol1.upper(), symbol2.upper()
    conn = get_db()

    def fetch_closes(symbol, n):
        rows = conn.execute("""
            SELECT date, close, daily_return FROM stock_data
            WHERE symbol=? ORDER BY date DESC LIMIT ?
        """, (symbol, n)).fetchall()
        return list(reversed(rows))

    d1 = fetch_closes(s1, days)
    d2 = fetch_closes(s2, days)
    conn.close()

    if not d1:
        raise HTTPException(status_code=404, detail=f"No data for {s1}")
    if not d2:
        raise HTTPException(status_code=404, detail=f"No data for {s2}")

    # Normalize to base 100
    base1 = d1[0][1]
    base2 = d2[0][1]
    norm1 = [{"date": r[0], "normalized": round(r[1] / base1 * 100, 3), "close": r[1]} for r in d1]
    norm2 = [{"date": r[0], "normalized": round(r[1] / base2 * 100, 3), "close": r[1]} for r in d2]

    # Correlation
    returns1 = [r[2] for r in d1]
    returns2 = [r[2] for r in d2]
    min_len = min(len(returns1), len(returns2))
    if min_len > 1:
        import numpy as np
        corr = float(round(float(pd.Series(returns1[:min_len]).corr(pd.Series(returns2[:min_len]))), 4))
    else:
        corr = None

    # Overall return over period
    overall1 = round((d1[-1][1] - d1[0][1]) / d1[0][1] * 100, 2)
    overall2 = round((d2[-1][1] - d2[0][1]) / d2[0][1] * 100, 2)
    winner = s1 if overall1 > overall2 else s2

    return {
        "comparison": {
            symbol1: {
                "start_price": round(d1[0][1], 2),
                "end_price": round(d1[-1][1], 2),
                "return_pct": overall1,
                "data": norm1,
            },
            symbol2: {
                "start_price": round(d2[0][1], 2),
                "end_price": round(d2[-1][1], 2),
                "return_pct": overall2,
                "data": norm2,
            },
        },
        "analysis": {
            "correlation": corr,
            "correlation_meaning": (
                "Strong positive correlation" if corr and corr > 0.7 else
                "Moderate correlation" if corr and corr > 0.3 else
                "Weak/no correlation" if corr else "N/A"
            ),
            "better_performer": winner,
            "period_days": days,
        }
    }


# ─── Bonus: GET /gainers-losers ────────────────────────────────────────────────
@app.get("/gainers-losers", summary="Top gainers and losers today")
def gainers_losers():
    """Returns top 3 gainers and top 3 losers based on latest daily return."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT s.symbol, c.name, s.daily_return, s.close
        FROM stock_data s JOIN companies c ON s.symbol=c.symbol
        WHERE s.date = (SELECT MAX(date) FROM stock_data WHERE symbol=s.symbol)
        ORDER BY s.daily_return DESC
    """)
    rows = c.fetchall()
    conn.close()

    gainers = [{"symbol": r[0], "name": r[1], "return_pct": round(r[2], 3), "close": r[3]} for r in rows[:3]]
    losers  = [{"symbol": r[0], "name": r[1], "return_pct": round(r[2], 3), "close": r[3]} for r in rows[-3:]]

    return {"top_gainers": gainers, "top_losers": list(reversed(losers))}


# ─── Serve static files (frontend) ────────────────────────────────────────────
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "📈 Stock Dashboard API running! Visit /docs for Swagger UI"}
