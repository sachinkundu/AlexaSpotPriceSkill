# CLAUDE.md

## Project Overview

AlexaSpotPriceSkill is an AWS Lambda-based Alexa Skill that reports Finnish electricity spot prices using the [Spot-hinta API](https://api.spot-hinta.fi). Users can ask about current prices, cheapest times, prices at specific hours, and whether it's a good time to run high-consumption appliances.

## Repository Structure

```
AlexaSpotPriceSkill/
├── lambda_function.py      # Lambda entry point; routes Alexa intents to handlers
├── spot_price_api.py       # HTTP client for Spot-hinta API (fetch/parse price data)
├── ssml_builder.py         # Generates SSML speech responses for each intent
├── utils.py                # Date/time parsing and formatting helpers
├── interaction_model.json  # Alexa skill interaction model (intents, slots, utterances)
├── deploy.sh               # Bash script to package and deploy to AWS Lambda
├── requirements.txt        # Python dependencies
├── tests/
│   ├── test_api.py                         # API fetching and parsing tests
│   ├── test_utils.py                       # Utility function tests
│   ├── test_lambda.py                      # Lambda handler routing tests
│   ├── test_ssml_builder.py                # SSML response generation tests
│   └── test_cheapest_tomorrow_before_2pm.py # Edge case: 2 PM cutoff logic
```

## Language and Runtime

- **Language:** Python 3 (3.11+)
- **Runtime:** AWS Lambda
- **No type hints** in production code; no linting or formatting tools configured

## Key Commands

### Run tests
```bash
pytest
```

Tests run from the project root. No `pytest.ini` or `pyproject.toml` config exists; pytest discovers tests in the `tests/` directory automatically.

### Deploy to AWS Lambda
```bash
./deploy.sh
```
Requires: AWS CLI with valid credentials, `pip`, `zip`. Optionally uses ASK CLI to update the Alexa interaction model.

### Install dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Intent Routing

`lambda_function.py` receives Alexa events and routes them by intent name:

| Intent | Handler | Description |
|--------|---------|-------------|
| `GetSpotPriceIntent` | `ssml_builder.get_spot_price_ssml()` | Current price + next 3 hours |
| `CheapestPriceIntent` | `ssml_builder.get_cheapest_price_ssml(date)` | Cheapest hour today/tomorrow |
| `GetSpotPriceAtHourIntent` | `ssml_builder.get_spot_price_at_hour_ssml(date, time)` | Price at a specific hour |
| `ShouldIRunMachineIntent` | `ssml_builder.get_run_machine_ssml()` | Recommends 3-hour cheap windows |
| `AMAZON.FallbackIntent` | Same as GetSpotPriceIntent | Fallback behavior |

### Data Flow

1. `spot_price_api.py` fetches hourly prices from `https://api.spot-hinta.fi/TodayAndDayForward`
2. Returns `(entries, error_message)` tuples — `entries` is a list of `{"dt": datetime, "price": float}` dicts
3. `ssml_builder.py` processes entries and generates SSML speech markup
4. `lambda_function.py` wraps SSML in Alexa response format via `build_ssml_response()`

### Important Domain Rules

- **Prices:** API returns EUR; code converts to cents (`price * 100`), formatted to 1 decimal place
- **Tomorrow's prices:** Not available before 2 PM — the skill returns a "check back later" message
- **Machine recommendation threshold:** 7 cents/kWh — looks for 3 consecutive hours all at or below this
- **Timezone handling:** API times are converted from UTC to local Finnish timezone throughout
- **Closing cues:** Each intent response gets a randomized closing phrase (8 variations) to avoid repetition

## Testing Patterns

- **Framework:** pytest with `monkeypatch` fixture for mocking
- **API mocking:** Tests monkeypatch `spot_price_api.fetch_all_price_entries` or `get_price_entries` to return deterministic data
- **Time mocking:** Tests use `FakeDateTime` classes patched onto `ssml_builder.datetime` to control `datetime.now()`
- **Assertions:** Tests verify exact SSML fragments (e.g., `<say-as interpret-as="cardinal">5.0</say-as>`)
- **No external calls:** All tests are fully isolated from the network

## Code Conventions

- Snake_case for all Python functions and variables
- PascalCase for Alexa intent names (e.g., `GetSpotPriceIntent`)
- Error handling uses `(result, error_message)` tuple pattern — check `error` before using `result`
- No classes — all modules are procedural with module-level functions
- Imports use `from datetime import datetime, timezone` style (not `import datetime`)
- SSML strings are built inline with f-strings, not via a templating library

## Deployment

- **Lambda function name:** `AlexaSpotPriceSkill`
- **Alexa Skill ID:** `amzn1.ask.skill.218b17ac-e2ef-493e-9ca8-571ac72d8ecd`
- **Packaging:** ZIP archive with dependencies bundled (no Lambda Layers)
- **No CI/CD pipeline** — deployment is manual via `deploy.sh`
