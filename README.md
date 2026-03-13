# Algorithmic Trading System

A low-latency automated trading system integrating NinjaTrader 8 with Interactive Brokers (IBKR) via a Python execution backend. Achieved a **73% win rate** executing **500+ trades daily** with a **2.75 profit factor** in backtests.

## Architecture

```
NinjaTrader 8 (C# Strategy)
        │
        │  HTTP POST (signal: buy/sell, symbol, quantity, bid/ask)
        ▼
Python Flask Server (localhost:5000)
        │
        ├── ThreadPoolExecutor (concurrent order execution)
        │
        ▼
IBKR TWS / Gateway (Interactive Brokers API)
        │
        ▼
NASDAQ Live Orders + Discord Webhook Notifications
```

The system decouples signal generation from order execution. NinjaTrader handles charting, indicator computation, and strategy logic in C#. The Python backend handles the IBKR connection, order lifecycle management, and real-time Discord notifications.

## Components

### `strategies/MyNinZaRenkoStrategy.cs`
NinjaTrader 8 strategy built on NinZaRenko bars with multi-indicator confluence entry logic:

**Entry conditions (all must be met):**
- MACD histogram above zero and MACD line above signal line
- Price above EMA(200), SMA(200), EMA(9), and VWAP
- OBV trending upward (volume confirmation)
- Two consecutive closes above EMA(20)

**Exit logic:**
- Partial profit: scales out 25 shares at +0.15 increments above entry
- Hard stop: exits if price drops 0.10 below last partial profit level
- Full exit: two consecutive closes below EMA(20)

### `src/Server.py`
Flask server bridging NinjaTrader signals to IBKR. Handles concurrent order submission via `ThreadPoolExecutor` with a 32-thread Waitress WSGI deployment. Manages buy/sell routing and partial profit sell flows with timeout fallback logic.

### `src/NinjaTraderBOT.py`
IBKR TWS API client. Implements limit order placement with configurable offset, an 8-second sell timeout with progressive price adjustment, and Discord webhook notifications on fill with order metadata.

## Setup

**Prerequisites:**
- Interactive Brokers TWS or IB Gateway running on port 7497
- NinjaTrader 8 with NinZaRenko licence
- Python 3.10+

```bash
git clone https://github.com/evans-onomerike/algorithmic-trading-system
cd algorithmic-trading-system
pip install -r requirements.txt
cp .env.example .env
# Add your Discord webhook URL to .env
```

**Run the execution server:**
```bash
python src/Server.py
```

**Import the strategy:**
Load `strategies/MyNinZaRenkoStrategy.cs` into NinjaTrader via Tools → Edit NinjaScript → Strategy.

## Results

| Metric | Value |
|--------|-------|
| Win Rate | 73% |
| Profit Factor | 2.75 |
| Daily Trades | 500+ |
| Order Latency | Sub-millisecond |
| Market Signals/min | 1,000+ |

## Notes

Model weights (`.pth`) and historical data (`.csv`) are excluded from this repository via `.gitignore`. The system was backtested on NASDAQ equities using 1-minute NinZaRenko bars.
