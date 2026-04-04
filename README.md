# 📈 Stock Data Intelligence Dashboard

A mini financial data platform for Indian stock market (NSE) data.  
Built with **FastAPI + SQLite + Chart.js** as part of the JarNox Internship Assignment.

---

## 🚀 Quick Start

```bash
# 1. Clone / navigate to project
cd stock_dashboard

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
uvicorn main:app --reload --port 8000

# 4. Open browser
# Dashboard → http://localhost:8000
# Swagger Docs → http://localhost:8000/docs
```

> **First run** will automatically fetch ~1 year of stock data via yfinance (~30 seconds).

---

## 🧱 Project Structure

```
stock_dashboard/
├── main.py              # FastAPI app with all endpoints
├── data_collector.py    # Data pipeline (fetch → clean → store)
├── stocks.db            # SQLite database (auto-created)
├── requirements.txt
├── README.md
└── static/
    └── index.html       # Frontend dashboard
```

---

## ⚙️ Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Language   | Python 3.10+                      |
| Backend    | FastAPI                           |
| Database   | SQLite (via sqlite3 stdlib)       |
| Data       | yfinance, Pandas, NumPy           |
| Frontend   | HTML + Vanilla JS + Chart.js      |
| Docs       | Swagger UI (auto via FastAPI)     |

---

## 📡 API Endpoints

| Endpoint                          | Method | Description                             |
|-----------------------------------|--------|-----------------------------------------|
| `/companies`                      | GET    | List all companies with latest stats    |
| `/data/{symbol}?days=30`          | GET    | Last N days of OHLCV + metrics          |
| `/summary/{symbol}`               | GET    | 52-week High/Low/Avg + best/worst days  |
| `/compare?symbol1=X&symbol2=Y`    | GET    | Normalized comparison + correlation     |
| `/gainers-losers`                 | GET    | Top 3 gainers and losers (bonus)        |
| `/docs`                           | GET    | Interactive Swagger UI                  |

### Example calls

```bash
curl http://localhost:8000/companies
curl http://localhost:8000/data/TCS?days=90
curl http://localhost:8000/summary/INFY
curl "http://localhost:8000/compare?symbol1=INFY&symbol2=TCS&days=30"
```

---

## 📊 Data Metrics Explained

### Standard Metrics (Part 1)
| Metric           | Formula                                  |
|------------------|------------------------------------------|
| Daily Return %   | `(CLOSE - OPEN) / OPEN × 100`           |
| 7-day Moving Avg | Rolling mean of last 7 close prices      |
| 52-week High/Low | Max(high) / Min(low) over past 365 days  |

### 🔬 Custom Metric: Volatility Score
A normalized score (0–100) measuring how "wild" a stock's price moves:

```
rolling_std(close, 14) / rolling_mean(close, 14) × 100
→ Min-max normalized to [0, 100]
```

| Score Range | Interpretation        |
|-------------|----------------------|
| 0 – 30      | Low volatility (stable stock) |
| 30 – 60     | Medium volatility    |
| 60 – 100    | High volatility (risky) |

This helps investors understand **risk** alongside return — a stock with 5% return and score=10 is far safer than one with 5% return and score=85.

---

## 🎨 Dashboard Features

- **Left Sidebar**: All companies with live price and return %
- **Price Chart**: Close price + 7-day MA overlay
- **Return Bar Chart**: Green for positive days, red for negative
- **Volatility Chart**: Custom metric visualized over time
- **52-Week Stats**: High, Low, Avg, Best/Worst trading day
- **Top Gainers / Losers**: Always visible overview
- **Compare Mode**: Normalized comparison chart + correlation coefficient
- **Time Filters**: 7D / 30D / 90D / 6M / 1Y

---

## 🏗️ Data Pipeline

```
yfinance API
    ↓
Raw OHLCV DataFrame (1 year)
    ↓
Clean: ffill missing, fix types
    ↓
Calculate: Daily Return, 7-day MA, Volatility Score
    ↓
Store in SQLite
    ↓
FastAPI serves data
    ↓
Chart.js visualizes it
```

Fallback: If yfinance fails (network/rate limit), realistic mock data is auto-generated using seeded random walks — so the app always works.

---

## 📦 Covered Stocks

| Symbol      | Company                  | Sector   |
|-------------|--------------------------|----------|
| RELIANCE    | Reliance Industries      | Energy   |
| TCS         | Tata Consultancy Services| IT       |
| INFY        | Infosys                  | IT       |
| HDFC        | HDFC Bank                | Banking  |
| WIPRO       | Wipro                    | IT       |
| TATASTEEL   | Tata Steel               | Steel    |
| HCLTECH     | HCL Technologies         | IT       |
| BAJFINANCE  | Bajaj Finance            | Finance  |

---

## 🧠 Design Decisions

1. **SQLite over PostgreSQL**: Zero setup friction for assignment; swap to PostgreSQL by changing the connection string in production.
2. **Mock fallback**: yfinance has rate limits; mock data ensures the app always demonstrates full functionality.
3. **FastAPI over Flask**: Auto-generates Swagger docs, has better async support, and type validation via Pydantic.
4. **Normalized comparison**: Base-100 normalization makes comparing ₹200 stocks vs ₹3000 stocks fair.

---

## 🔮 Potential Extensions

- [ ] Deployment on Render / Railway
- [ ] Docker container
- [ ] ML price prediction (LinearRegression on MA features)
- [ ] WebSocket for live price updates
- [ ] User watchlist (auth + DB)
- [ ] Sentiment index from news headlines (NewsAPI)
uvicorn main:app --reload --port 8000