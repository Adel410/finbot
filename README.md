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

Configuration defaults are centralized in `config/settings.py`. The
`config/.env.example` file documents names reserved for future configuration;
no environment loader or external service is required in this sprint.

Select the market source before running FinBot. Simulated data remains the safe,
offline default:

```powershell
$env:MARKET_DATA_PROVIDER="simulated"  # or "yfinance"
python -m finbot
```

The yfinance mode requires network access and fails explicitly if a symbol has
no usable history, a value is missing or invalid, or the remote request fails.

## AI provider preparation

Sprint 3A keeps `AI_PROVIDER=simulated` as the default. The provider contract,
factory, generic prompts, and local audit format are ready for future providers.
The Grok class is deliberately non-operational: it has no xAI dependency, no
HTTP code, and every analysis attempt raises `NotImplementedError`.

No xAI account or API key is needed. No real AI request or AI expense is possible
in this sprint. Simulated audit records contain the provider, model, prompts, and
zero values for requests, tokens, and cost; these generated files are ignored in
`data/usage`.

## Test

```powershell
python -m pytest
```
