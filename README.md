# Miami Comp Engine Toolkit

Miami Real Estate Comp Engine support toolkit.

Free, public Miami-Dade property data + the Miami Comp Engine HTTP API.
No paid data vendor anywhere in this stack. Everything is county public records.

## What is in here

| Path | What it does |
|---|---|
| `docs/data-sources.md` | Exact endpoints, form fields, and bot-wall workarounds for the 3 free county sources |
| `docs/engine-api.md` | Miami Comp Engine HTTP API: pull comps, push new sales, run valuations |
| `scripts/auction_scraper.py` | Pure `httpx`. Foreclosure + tax-deed auction calendar (realforeclose). Runs anywhere, no browser |
| `scripts/county_pa.py` | Property Appraiser lookup: owner, folio, SF, values, subdivision, zoning |
| `scripts/clerk_lp_screen.py` | Clerk official-records name screen: lis pendens, tax liens, judgments, liens |

## Quickstart for Codex

```bash
pip install -r requirements.txt
playwright install chromium
```

- `auction_scraper.py` works as-is with plain httpx.
- `county_pa.py` and `clerk_lp_screen.py` now use `scripts/browser_util.py`,
  a plain Playwright persistent browser context:

```python
from playwright.async_api import async_playwright

async def get_browser_context():
    pw = await async_playwright().start()
    return await pw.chromium.launch_persistent_context(
        user_data_dir="./browser-profile",
        headless=False,          # headful survives Turnstile far better
        args=["--disable-blink-features=AutomationControlled"],
    )
```

Run from a residential connection; the county sites rate-limit and challenge
datacenter IPs aggressively.

## Engine access

Copy `.env.example` to `.env` and put the API key there:

```powershell
Copy-Item .env.example .env
notepad .env
```

Then test the engine client:

```powershell
python scripts/engine_client.py comp "590 Lakeview Dr, Miami Beach, FL 33140"
python scripts/engine_client.py value "590 Lakeview Dr, Miami Beach, FL 33140"
```

Keep `.env` private. Do not paste the key into chat, Slack, or source files.

## Farm markets (Caleb's buy box)

Bal Harbour, Bay Harbor Islands, Keystone Point / N Miami, Miami Beach.
Zips: 33139, 33140, 33141, 33154, 33181.

## Rules that keep this data trustworthy

1. NEVER invent a comp. Every sale row must come from county records or a classified scrape with a source tag.
2. Verify name-search hits against Property Appraiser ownership before treating them as matches (common names).
3. Engine updates go through `POST /api/import-sales` with `x-engine-key` (see `docs/engine-api.md`). Ask Caleb for the key.
