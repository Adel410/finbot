# FinBot project rules

- Keep the code compatible with Python 3.10 or newer.
- Prefer small, direct modules and avoid unnecessary abstractions.
- Use Pydantic for data models and strict validation boundaries.
- Keep automated tests current and run the full suite after changes.
- Store generated run artifacts only in `data/runs` and do not commit them.
- Centralize runtime defaults in `config/settings.py`.
- Use the standard logging setup for runtime information instead of `print()`.
- Keep `simulated` as the default market-data provider so tests remain offline.
- Mock yfinance responses in tests; never make the test suite depend on Internet.
- Never replace failed real-market collection with simulated data silently.
- Keep AI providers behind the provider contract and factory.
- Use only the official xAI SDK for Grok and keep all tests fully mocked offline.
- Check the monthly budget before every real AI request; never retry silently.
- Never log or persist API keys or authorization headers.
- Give every execution and its audit the same non-sensitive `run_id`.
- Keep run metadata explicit for both market-data and AI providers.
- Use zero usage metrics and `actual_cost_usd=null` for simulated AI runs.
- Store the exact collected market-data snapshot in every successful run.
- Warn at 80% of locally audited monthly xAI spend and block at 100% before calls.
- Treat the local cost limit as a risk reduction, not an absolute guarantee.
- Keep failure audits structured and sanitized; never persist stack traces.
- Keep the risk engine deterministic and independent from AI providers and networks.
- Use `Decimal`, never `float`, for portfolio, order, price, and risk calculations.
- Never let AI confidence bypass risk limits or make the risk engine execute orders.
- Evaluate risk batches sequentially against an internal projected portfolio.
- Never mutate the caller's Portfolio while projecting approved buys and sells.
- Do not add real trading, broker access, external market data, or AI API calls
  unless a future task explicitly requests them.
- Never execute a real financial transaction.

Never commit:

- API keys
- `.env` files
- secrets
- credentials
- generated logs
- usage tracking files
- private configuration

Only `.env.example` may be tracked.
