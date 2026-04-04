"""
Data Collection & Preparation Module
Fetches real stock data using yfinance, cleans it, and stores in SQLite
"""

import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Indian stocks (NSE symbols with .NS suffix for yfinance)
COMPANIES = {
    "RELIANCE": {"name": "Reliance Industries", "symbol": "RELIANCE.NS", "sector": "Energy"},
    "TCS":      {"name": "Tata Consultancy Services", "symbol": "TCS.NS", "sector": "IT"},
    "INFY":     {"name": "Infosys", "symbol": "INFY.NS", "sector": "IT"},
    "HDFC":     {"name": "HDFC Bank", "symbol": "HDFCBANK.NS", "sector": "Banking"},
    "WIPRO":    {"name": "Wipro", "symbol": "WIPRO.NS", "sector": "IT"},
    "TATASTEEL":{"name": "Tata Steel", "symbol": "TATASTEEL.NS", "sector": "Steel"},
    "HCLTECH":  {"name": "HCL Technologies", "symbol": "HCLTECH.NS", "sector": "IT"},
    "BAJFINANCE":{"name": "Bajaj Finance", "symbol": "BAJFINANCE.NS", "sector": "Finance"},
}

DB_PATH = "stocks.db"


def init_db():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            daily_return REAL,
            ma_7 REAL,
            volatility_score REAL,
            UNIQUE(symbol, date)
        )
    """)

    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")


def calculate_volatility_score(closes: pd.Series, window=14) -> pd.Series:
    """
    Custom metric: Normalized Volatility Score (0-100)
    Based on rolling std dev relative to mean price
    Higher score = more volatile stock
    """
    rolling_std = closes.rolling(window=window, min_periods=1).std()
    rolling_mean = closes.rolling(window=window, min_periods=1).mean()
    raw_vol = (rolling_std / rolling_mean) * 100
    # Normalize between 0-100
    min_v, max_v = raw_vol.min(), raw_vol.max()
    if max_v == min_v:
        return pd.Series([50.0] * len(closes), index=closes.index)
    return ((raw_vol - min_v) / (max_v - min_v) * 100).round(2)


def fetch_and_store(symbol: str, company_info: dict):
    """Fetch 1 year of stock data, clean and store in DB"""
    logger.info(f"Fetching data for {symbol}...")

    try:
        ticker = yf.Ticker(company_info["symbol"])
        df = ticker.history(period="1y")

        if df.empty:
            logger.warning(f"⚠️ No data for {symbol}, generating mock data")
            df = generate_mock_data(symbol)
        else:
            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = ["open", "high", "low", "close", "volume"]
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.index = df.index.strftime("%Y-%m-%d")

    except Exception as e:
        logger.warning(f"⚠️ yfinance failed for {symbol}: {e}. Using mock data.")
        df = generate_mock_data(symbol)

    # Handle missing values
    df = df.ffill().bfill()
    df["volume"] = df["volume"].fillna(0).astype(int)

    # Calculated metrics
    df["daily_return"] = ((df["close"] - df["open"]) / df["open"] * 100).round(4)
    df["ma_7"] = df["close"].rolling(window=7, min_periods=1).mean().round(2)
    df["volatility_score"] = calculate_volatility_score(df["close"])

    # Store in DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Upsert company
    c.execute("INSERT OR REPLACE INTO companies VALUES (?,?,?)",
              (symbol, company_info["name"], company_info["sector"]))

    # Upsert stock data
    for date, row in df.iterrows():
        c.execute("""
            INSERT OR REPLACE INTO stock_data
            (symbol, date, open, high, low, close, volume, daily_return, ma_7, volatility_score)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (symbol, date, round(row["open"], 2), round(row["high"], 2),
              round(row["low"], 2), round(row["close"], 2),
              int(row["volume"]), row["daily_return"],
              row["ma_7"], row["volatility_score"]))

    conn.commit()
    conn.close()
    logger.info(f"✅ Stored {len(df)} rows for {symbol}")


def generate_mock_data(symbol: str) -> pd.DataFrame:
    """Generate realistic mock stock data as fallback"""
    np.random.seed(hash(symbol) % 1000)
    dates = pd.date_range(end=datetime.today(), periods=365, freq="B")
    base_price = np.random.uniform(200, 3000)
    returns = np.random.normal(0.0003, 0.015, len(dates))
    closes = base_price * np.cumprod(1 + returns)
    opens = closes * (1 + np.random.normal(0, 0.005, len(dates)))
    highs = np.maximum(opens, closes) * (1 + abs(np.random.normal(0, 0.008, len(dates))))
    lows = np.minimum(opens, closes) * (1 - abs(np.random.normal(0, 0.008, len(dates))))
    volumes = np.random.randint(500000, 10000000, len(dates))

    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": volumes
    }, index=dates.strftime("%Y-%m-%d"))
    return df.round(2)


def run_data_pipeline():
    """Full pipeline: init DB → fetch all companies → store data"""
    logger.info("🚀 Starting data pipeline...")
    init_db()
    for symbol, info in COMPANIES.items():
        fetch_and_store(symbol, info)
    logger.info("🎉 Data pipeline complete!")


if __name__ == "__main__":
    run_data_pipeline()
