# Miami Comp Engine HTTP API

Convex backend. Dev site URL: `https://judicious-cassowary-306.convex.site`
Ask Caleb for `ENGINE_API_KEY`; send it as header `x-engine-key` on the protected routes.

## Endpoints

### POST /api/comp  (x-engine-key)
Run a comp for an address against the verified sales DB (106+ classified sales
across Bal Harbour, Bay Harbor Islands, Keystone/N Miami, Miami Beach).

```bash
curl -X POST https://judicious-cassowary-306.convex.site/api/comp \
  -H "x-engine-key: $ENGINE_API_KEY" -H "content-type: application/json" \
  -d '{"address": "590 Lakeview Dr, Miami Beach, FL 33140"}'
```

### POST /api/value  (x-engine-key)
Full valuation: county facts + comp-weighted pricing (quartile $/SF by micro-market,
land floor, water-tier scoring, confidence grade A/B/C).

### POST /api/import-sales  (x-engine-key)
Bulk-add sale rows so the engine keeps learning. Dedupes by saleId. Max 500 rows/call.

Row shape (`SaleRow`):
```json
{
  "saleId": "unique-string",
  "address": "...", "unit": "", "city": "Miami Beach", "zip": "33140",
  "salePrice": 2450000, "saleDate": "2026-08-01",
  "livingSf": 2760, "lotSf": 9000, "yearBuilt": 1957, "beds": 4, "baths": 3,
  "propertyClass": "sfr",            // "sfr" | "condo"
  "waterType": "Canal",              // Canal | Open Bay | Canal/Bay | None | Verify
  "conditionClass": "renovated",     // or "original" | "teardown" | "unknown"
  "subdivision": "KEYSTONE ISLAND NO 3",
  "microMarket": "keystone",
  "verified": false,
  "source": "codex_county_scrape"
}
```

Rules:
- `propertyClass: "condo"` rows comp only against condos; SFR only against SFR.
- Condos without a unit number are unusable as comps; skip them.
- `verified: true` is reserved for county-confirmed sales (raise confidence grades).
- Water type vocabulary is fixed; "Verify" defaults to canal tier (safe side).

### POST /api/lead, /api/offer, /api/track  (x-engine-key)
Lead capture + offer tracking for the value funnel (calebault.com integration).

### GET /api/report?token=...
Fetch a generated valuation report by token.

### POST /api/offer-notified  (header: LEAD_SYNC_SECRET)
Mark an offer alert as synced (used by the Slack alert loop).

## Notes for agents

- Micro-market matching uses distinctive subdivision keywords; "harbor island" alone
  matches Bay Harbor Islands. Use distinctive keywords, bay_harbor_islands first.
- North Beach (e.g. 750 83 St) currently has no micro-market rules; county bands only.
- Engine confidence: A- needs 2 verified comps, B needs 3 comps incl 1 same-market, else C.
