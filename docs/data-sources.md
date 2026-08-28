# Miami-Dade free data sources (verified 2026-08-28)

## 1. Property Appraiser (owner, folio, values, SF, zoning)

Public JSON API behind https://www.miamidade.gov/Apps/PA/PApublication/

- Address search: `GET /PAWebService/WebServices/PAWebService.asmx/GetAddress?myAddress={street}&myUnit=&clientid=www.miamidade.gov`
  - EXACT street suffix match: "61 CAMDEN CT" works, "61 CAMDEN DR" returns 0. Try suffix variants, require house-number match.
  - Units: street + bare unit number, NO keywords: "10275 COLLINS AVE 1510" works, "APT 1510" fails.
  - County normalizes letter units to numbers (17D -> 1704). Letters are unrecoverable; return floor candidates.
  - NEVER strip trailing 5-digit numbers as zips: Collins Ave house numbers are 5 digits. Zip-strip must be end-anchored.
  - Street enumeration works: `myAddress=E BROADVIEW DR` returns every parcel on the street.
  - Pages cap at 200 rows; 201+ unit buildings need from/to pagination.
- Folio lookup: `GetPropertySearchByFolio?folioNumber={dashless folio}` (param is `folioNumber`, NOT `folio`).
- Bot wall: plain httpx from datacenter IPs now gets Akamai-blocked. A real browser (Playwright persistent profile) works. From a residential IP, httpx may still work; test first.

## 2. Clerk official records (lis pendens, liens, judgments, deeds)

https://onlineservices.miamidadeclerk.gov/officialrecords/Search.aspx

- Public "Name/Document" search. Browser REQUIRED (Cloudflare Turnstile blocks curl/httpx even with good headers).
- Form fields (confirmed): `lastName`, `firstName`, `middleName`, `documentType` (select), `dateRangeFrom`, `dateRangeTo` (MM/DD/YYYY), submit via `button[type="submit"]`.
- Results page: split raw text on `Clerk's File Number:`; per record parse Party Name / Document Type / Rec Date / Legal Description / CFN.
- Useful doc types for distress: LIS PENDENS, FEDERAL TAX LIEN, JUDGMENT, LIEN. Screen 2023+.
- Advanced search requires a login; the public name search does not.
- Browser sessions die after ~15 searches (TargetClosedError). Save progress after every name; on restart, skip completed entries and retry errored ones. A supervisor loop that reruns the script until all names have results is the proven pattern.
- False positives: common names (Rodriguez, Garcia) match strangers. Require first-name token in the Party string, then confirm by legal description (unit/lot) or by cross-checking owner on the Property Appraiser.
- Confirmation gold standard: legal description in the LP matches the lead's unit/lot.

## 3. Auction calendar (foreclosure + tax deed)

https://www.miamidade.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=MM/DD/YYYY

- Flow: GET the PREVIEW page for a date, then POST/GET the AJAX loader:
  `index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=W&PageDir=0&doR=1&bypassPage=1`
- CRITICAL: use a FRESH httpx session per date. The backend keys results by IP/session; reusing a session returns the wrong date's data.
- Paginate with `PageDir=1&bypassPage=0` until the returned list repeats.
- `retHTML` is token-obfuscated. Split on `<div id="AITEM_\d+"` and regex-parse fields (case number, parcel/folio, address, plaintiff, judgment, auction type, date).
- ~25% of items are non-real-estate (no parcel); skip them.
- Auction types: FORECLOSURE and TAXDEED both come through this feed.
- Sales info per folio: PA `SalesInfos` via folio lookup (source 1) for last-sale price/date.

## Blocked sources (do not waste time)

- miamidade.county-taxes.com (tax certificates): Cloudflare-walled.
- realtaxdeed.com: times out. Tax-deed items come via realforeclose instead.
- Redfin `/page-N` sold pages silently redirect to page 1 (~43 cards max per window); the gis-csv download URL is JS-built and expect_download times out.
