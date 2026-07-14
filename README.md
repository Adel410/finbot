# FinBot

FinBot is currently a small research pipeline. By default it loads fixed market
data for AAPL, MSFT, and NVDA, passes it to a deterministic simulated AI
provider, validates the decisions with Pydantic, and stores each run as JSON.
The processing stages are explicit: market collection, prompt construction,
simulated AI analysis, validation, and local storage. Runtime information is
written to a daily file in `logs` and displayed in the console.

An optional yfinance collector can retrieve daily closing data. No real AI,
broker, database, or trading system is connected, and FinBot cannot execute a trade.

## Requirements

- Python 3.10 or newer

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

From the project root, with the environment activated:

```powershell
python -m finbot
```

Generated files are written to `data/runs`.

Configuration defaults and validation are centralized in `config/settings.py`.
The ignored `.env` file holds private AI configuration; only
`config/.env.example` is tracked.

Select the market source before running FinBot. Simulated data remains the safe,
offline default:

```powershell
$env:MARKET_DATA_PROVIDER="simulated"  # or "yfinance"
python -m finbot
```

The yfinance mode requires network access and fails explicitly if a symbol has
no usable history, a value is missing or invalid, or the remote request fails.

## AI providers

`AI_PROVIDER=simulated` remains the default. Grok uses the official xAI Python
SDK only and sends one structured request for all collected symbols. Configure
the ignored `.env` file with `AI_PROVIDER`, `XAI_API_KEY`, `XAI_MODEL`,
`XAI_DRY_RUN`, and `MAX_MONTHLY_API_COST_USD`.

When `XAI_DRY_RUN=true`, no xAI client or request is created. Before a real
request, FinBot checks current-month audited spend against the configured limit.
Successful calls record prompts, the raw non-sensitive response, token counts,
estimated and reported cost, and duration under ignored `data/usage` files.
API keys and request headers are never audited or logged.

## Supported provider combinations

1. Simulated market data + simulated AI: fully local and deterministic.
2. yfinance market data + simulated AI: real daily prices, local decisions.
3. Simulated market data + Grok: real AI over fixed offline prices.
4. yfinance market data + Grok: real prices and real AI.

The first paid validation in Sprint 3B tested combination 3, simulated market
data with Grok. Combination 4 has not yet been validated with a real xAI call.

Every run JSON records a random non-sensitive `run_id`, both providers, model,
dry-run state, requests, tokens, costs, duration, and decisions. The matching
audit file uses the same `run_id`. For simulated AI, the documented convention
is zero requests, tokens, estimated cost, and duration, with `actual_cost_usd`
set to `null`.

## Test

```powershell
python -m pytest
```
