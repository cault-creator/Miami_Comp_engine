# Miami Luxury Comping And Seller Opportunity Playbook

## Operating Goal

Build a Miami luxury real estate expert workflow that combines disciplined comps
with public-record distress discovery. The core idea is simple: value the asset
like an expert, then prioritize sellers where timing, equity, and motivation may
create an opportunity.

## Comp Discipline

Separate facts from judgment on every valuation.

Facts:

- Folio, legal description, subdivision, zoning, living SF, lot SF, year built.
- Closed sale price, sale date, property class, source, and verification status.
- Waterfront tier, unit number for condos, and sales history.

Judgment:

- Renovation quality.
- Teardown probability.
- Water premium.
- Micro-market boundary.
- Seller motivation.

Never average weak comps. Rank them by similarity, recency, verification, and
market relevance.

## Buy Box

Start with:

- Bal Harbour
- Bay Harbor Islands
- Keystone Point / North Miami
- Miami Beach
- ZIPs: 33139, 33140, 33141, 33154, 33181

Treat each micro-market as its own pricing universe. Same ZIP is weaker than
same subdivision, same water tier, and same buyer pool.

## Distress Signals

Use distress as a lead-priority signal, not proof that someone wants to sell.

High-priority signals:

- Foreclosure auction with parcel and address match.
- Lis pendens matched by owner name and legal description.
- Federal tax lien or judgment tied to the same owner.
- Divorce or probate indicator confirmed through public records.
- Out-of-area mailing address plus deferred maintenance or long ownership.
- Homestead mismatch, investor ownership, or long hold with meaningful equity.

False-positive rule: common names are dangerous. Match owner name, property
address or legal description, and folio before treating a record as actionable.

## Daily Data Routine

1. Pull the auction calendar for the next 30-45 business days.
2. Enrich parcels through Miami-Dade Property Appraiser.
3. Screen owners through Clerk official records for 2023+ distress docs.
4. Push county-confirmed sale rows into the comp engine.
5. Run valuations on candidate seller addresses.
6. Manually review high-equity/high-distress leads before outreach.

## Starting Lead Score

- Equity cushion: 0-30
- Distress signal strength: 0-30
- Luxury buy-box fit: 0-20
- Comp confidence: 0-10
- Contactability/manual confidence: 0-10

Work leads above 70 manually first. Below that, collect more evidence before
spending attention.

## Guardrails

- Do not invent comps.
- Do not treat a clerk name hit as a match until ownership or legal description
  is confirmed.
- Do not use private credentials in chat.
- Do not attempt authentication or bypass blocked public sites.
- Keep outreach paused until a human reviews the lead evidence.
