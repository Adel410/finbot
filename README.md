# FinBot

FinBot is currently a small research pipeline. By default it loads fixed market
data for AAPL, MSFT, and NVDA, passes it to a deterministic simulated AI
provider, validates the decisions with Pydantic, and stores each run as JSON.
The processing stages are explicit: market collection, prompt construction,
simulated AI analysis, validation, and local storage. Runtime information is
written to a daily file in `logs` and displayed in the console.

An optional yfinance collector can retrieve daily closing data, and Grok is
available through the official xAI SDK. No broker or real trading system is
connected. FinBot remains an experimental research platform and cannot execute
a trade.

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
dry-run state, requests, tokens, costs, duration, the exact market-data snapshot,
and decisions. The matching audit file uses the same `run_id`. For simulated AI,
the documented convention is zero requests, tokens, estimated cost, and duration,
with `actual_cost_usd` set to `null`.

The local monthly budget guard checks already-audited spend before each call,
warns at 80%, and blocks new calls once the recorded total has reached the limit.
The exact cost of the current call is known only after its response, so that call
can take the total slightly above the configured limit. This reduces risk but is
not an absolute spending guarantee and does not replace limits, alerts, or other
protections configured on the xAI account.

Failed provider calls receive a structured local audit containing the run ID,
UTC timestamp, provider, model, safe error type/message, duration, known usage,
and prompts. It never stores credentials, headers, stack traces, or API keys.

## Test

```powershell
python -m pytest
```

## Offline risk engine

`RiskEngine` is a deterministic, AI-independent authority that evaluates
validated `BUY`, `SELL`, and `HOLD` recommendations against an explicit
long-only portfolio and current prices supplied by the caller. It uses `Decimal`
throughout, caps new orders and position exposure, respects available cash and
minimum order value, optionally supports fractional shares, rejects short sales,
and sells an existing position in full.

The engine evaluates a decision batch sequentially against an internal projected
portfolio: each approved buy consumes projected cash and each approved full sale
releases it before the next decision. The input portfolio remains unchanged.
It only proposes risk-approved order quantities; it does not execute orders and
is not automatically connected to the AI pipeline. There is no broker
or complete paper-trading engine in this sprint. Partial sales, leverage, margin,
fees, slippage, stops, portfolio optimization, and market-data retrieval are out
of scope. Existing positions must all have a positive caller-supplied market
price so portfolio valuation cannot silently be incomplete.
