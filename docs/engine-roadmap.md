# Miami Comp Engine Roadmap

## Goal

Turn the current comp engine into a professional Miami luxury valuation and
opportunity system. The engine should ingest public property/sales records,
classify the asset, select defensible comps, value multiple exit strategies, and
produce an analyst-grade explanation with evidence.

## Data Layers

### 1. Parcel Master

One row per folio.

Fields:

- folio
- site address
- owner name
- mailing address
- subdivision
- municipality
- zip
- zoning
- legal description
- living SF
- adjusted SF
- lot SF
- year built
- beds
- baths
- pool
- dock
- waterfront type
- homestead
- assessed value
- market value
- last county refresh date

### 2. Sales Ledger

One row per recorded sale.

Fields:

- saleId
- folio
- address
- unit
- property class
- sale date
- sale price
- grantor
- grantee
- deed/document reference
- verified county sale flag
- arms-length/qualified flag
- source
- imported at

### 3. Comp Feature Table

Derived fields used for scoring.

Fields:

- microMarket
- buyer pool
- property class
- waterfront tier
- condition class
- teardown likelihood
- renovation age estimate
- effective year
- land value floor
- $/living SF
- $/lot SF
- recency bucket
- same-subdivision flag
- same-water flag
- same-property-class flag
- confidence flags

### 4. Distress And Opportunity Table

One row per public-record signal.

Fields:

- folio
- owner
- signal type
- document type
- recorded date
- case number or CFN
- legal description excerpt
- match confidence
- source URL
- verified flag
- notes

Signal types:

- foreclosure auction
- tax deed auction
- lis pendens
- federal tax lien
- judgment
- code lien
- probate indicator
- divorce indicator
- absentee owner
- long-hold equity

## Data Loading Plan

### Previous Sales

Use Miami-Dade Property Appraiser sales history as the first trusted source.

Workflow:

1. Enumerate target streets/subdivisions/folios in the buy box.
2. Fetch parcel facts by folio or address.
3. Extract sales history from each parcel.
4. Normalize sales into `SaleRow`.
5. Skip non-arms-length sales when they can be identified.
6. Mark county-confirmed records as `verified: true`.
7. Send rows to `/api/import-sales` in batches of 500 or fewer.

### Current Sales

Current sales should be refreshed on a schedule.

Workflow:

1. Nightly or weekly refresh of target folios.
2. Compare latest sales history against the local sales ledger.
3. Import new county-confirmed sales.
4. Flag new sales that need condition/waterfront classification.
5. Recompute micro-market quartiles and confidence bands.

### Active Opportunity Data

Workflow:

1. Pull foreclosure/tax-deed auction calendar 30-45 business days forward.
2. Enrich each parcel through Property Appraiser.
3. Screen current owner through Clerk official records.
4. Confirm matches by owner plus legal description or folio.
5. Score opportunity only after parcel and distress signal are verified.

## Comp Selection Logic

Rank comps instead of averaging broad search results.

Suggested scoring:

- Same property class: required
- Same micro-market: +30
- Same subdivision: +20
- Same waterfront tier: +20
- Sale within 6 months: +15
- Sale within 12 months: +8
- Living SF within 20%: +10
- Lot SF within 25%: +8
- Same condition class: +12
- Verified county sale: +10
- Non-arms-length or suspicious sale: exclude or heavy penalty

The comp set should expose:

- best 3 comps
- backup comps
- excluded comps with reason
- confidence grade
- low/base/high value range

## Valuation Modes

### Land Value

Use when the improvement is obsolete or teardown likely.

Inputs:

- lot SF
- waterfront tier
- zoning
- recent land/teardown sales
- buildable envelope
- demolition and carrying cost

Outputs:

- land floor
- premium land value
- developer max basis

### Fix And Flip

Use when the property is structurally viable but under-improved.

Inputs:

- as-is value
- after-repair value
- rehab scope
- construction budget
- selling costs
- financing/carrying costs
- target profit margin

Outputs:

- ARV
- max purchase price
- expected profit
- downside case

### Rehab Buy And Hold

Use when rental or long-term appreciation supports the basis.

Inputs:

- stabilized value
- renovation budget
- rent estimate
- taxes
- insurance
- HOA if applicable
- debt assumptions
- cap rate / yield target

Outputs:

- stabilized value
- max basis
- cash-on-cash estimate
- DSCR estimate

### Development

Use when zoning/lot attributes may support redevelopment.

Inputs:

- land value
- zoning/buildability
- likely product type
- hard costs
- soft costs
- entitlement timeline
- resale or rent assumptions
- developer margin

Outputs:

- residual land value
- max land bid
- risk grade

### End User Listing Market Value

Use when pricing for retail sale to an owner-user.

Inputs:

- best emotional/retail comps
- view/water premium
- finish quality
- school/neighborhood demand
- days on market
- active/pending competition if available

Outputs:

- recommended list range
- likely contract range
- appraisal risk
- buyer objection notes

## LLM Analyst Architecture

The LLM should not invent value. The engine calculates value ranges and comp
rankings; the LLM explains, audits, and challenges them.

### Inputs To The LLM

Provide structured JSON only:

- subject parcel facts
- selected comps with scores
- excluded comps with reasons
- sales statistics by micro-market
- distress/opportunity signals
- valuation-mode assumptions
- confidence flags
- source provenance

### LLM Tasks

The LLM should:

- explain why each comp is strong or weak
- identify missing data
- flag suspicious sales or mismatched comps
- produce broker-style valuation commentary
- write separate land, flip, hold, development, and retail listing views
- state assumptions and confidence
- recommend next verification steps

### LLM Guardrails

The LLM must:

- never create comps
- never override verified source facts
- never treat distress as certainty
- never provide legal advice
- never claim a lead is motivated without evidence
- always cite record/source IDs supplied by the engine

## Recommended API Additions

Add these endpoints to the engine:

- `POST /api/parcel/import`
- `POST /api/distress/import`
- `POST /api/valuation/analyze`
- `GET /api/parcel/:folio`
- `GET /api/market/:microMarket/stats`
- `GET /api/lead/:folio/evidence`

`/api/valuation/analyze` should return:

- machine valuation
- selected comps
- excluded comps
- LLM narrative
- confidence grade
- recommended next data checks

## Next Build Steps

1. Build a local sales ingestion script that converts PA sales history into
   engine `SaleRow` batches.
2. Add a `parcel_master.jsonl` cache so every valuation has subject facts.
3. Add a comp scoring module with explicit inclusion/exclusion reasons.
4. Add distress signal import and match-confidence scoring.
5. Add LLM analyst generation using structured JSON from the engine.
6. Build a review dashboard for high-value/high-distress leads.
