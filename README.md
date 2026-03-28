# BullVaan — Real-Time Options Trading Dashboard

A web-based trading dashboard for NSE/BSE index options with live market data, signal analysis, and an auto-trading engine.

![Market](https://img.shields.io/badge/Market-NSE%20%7C%20BSE-blue)
![Backend](https://img.shields.io/badge/Backend-FastAPI-green)
![Frontend](https://img.shields.io/badge/Frontend-React-blue)

---

## Tech Stack

| Layer          | Tech                                 |
| -------------- | ------------------------------------ |
| **Backend**    | Python, FastAPI, Uvicorn             |
| **Frontend**   | React                                |
| **Broker API** | Zerodha KiteConnect + KiteTicker     |
| **Database**   | Supabase (PostgreSQL)                |
| **Deployment** | Render (backend), Netlify (frontend) |

---

## Project Structure

````
BullVaan/
├── backend/
│   ├── api/
│   │   ├── server.py          # FastAPI routes and WebSocket endpoints
│   │   ├── login.py           # Authentication
│   │   └── signup.py          # User registration
│   ├── engine/                # Trading engine
│   ├── strategies/            # Technical analysis strategies
│   ├── utils/                 # Helpers (auth, data, logging)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/             # Dashboard, Trades, Charts, Login, Signup, etc.
│   │   ├── components/        # Reusable UI components
│   │   └── layout/            # Sidebar and routing
│   └── package.json
└── config/
---

## Pages

| Page               | Description                                              |
| ------------------ | -------------------------------------------------------- |
| **Dashboard**      | Live signals, market data, options overview, auto-trader |
| **Swing Trade**    | Nifty50 stock movers and premarket signals               |
| **Charts**         | Live candlestick charts (1m, 5m, 15m)                    |
| **Trades**         | Active and completed trades with live P&L                |
| **History**        | Trade history                                            |
| **Settings**       | User configuration                                       |
| **Login / Signup** | Authentication                                           |

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Zerodha KiteConnect API credentials
- Supabase project

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Copy and fill in your credentials
cp .env.example .env

uvicorn api.server:app --host 0.0.0.0 --port 8000
````

### Frontend

```bash
cd frontend
npm install
npm start   # Runs on port 3000

```
