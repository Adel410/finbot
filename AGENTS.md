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
- Grok must remain non-operational until a future task explicitly authorizes it.
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
