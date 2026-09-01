"""Import Miami-Dade PA sales history into the Miami Comp Engine.

The safe default is to write a reviewable JSON batch. Add --push only after you
have checked the output and configured ENGINE_API_KEY in .env.
"""
import argparse
import asyncio
import csv
import json
import re
from datetime import datetime
from pathlib import Path

from engine_client import engine_request


SALE_BATCH_LIMIT = 500
WATER_TYPES = {"Canal", "Open Bay", "Canal/Bay", "None", "Verify"}
CONDITION_CLASSES = {"renovated", "original", "teardown", "unknown"}


def clean_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    return int(re.sub(r"[^\d]", "", text)) if re.search(r"\d", text) else None


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def sale_date_iso(value):
    text = clean_text(value)
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def address_slug(value):
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:80] or "unknown-address"


def infer_unit(address, legal):
    text = f"{address} {legal}"
    patterns = [
        r"\b(?:unit|apt|apartment|suite|ste|#)\s*([a-z0-9-]+)\b",
        r"\bcondo(?:minium)?\s+(?:unit\s+)?([a-z0-9-]+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).upper()
    return ""


def infer_property_class(parcel, unit):
    text = " ".join(
        clean_text(parcel.get(k))
        for k in ("legal", "subdivision", "property_class", "propertyClass")
    ).upper()
    if unit or "CONDO" in text or "CONDOMINIUM" in text:
        return "condo"
    return "sfr"


def infer_water_type(parcel):
    existing = clean_text(parcel.get("waterType") or parcel.get("water_type"))
    if existing in WATER_TYPES:
        return existing
    text = " ".join(clean_text(parcel.get(k)) for k in ("legal", "subdivision")).upper()
    if "BAY" in text and ("CANAL" in text or "RIP" in text):
        return "Canal/Bay"
    if "BAY" in text:
        return "Open Bay"
    if parcel.get("has_dock") or parcel.get("riparian") or "CANAL" in text:
        return "Verify"
    return "None"


def infer_micro_market(parcel):
    text = " ".join(
        clean_text(parcel.get(k))
        for k in ("address", "city", "zip", "subdivision", "legal")
    ).upper()
    rules = [
        ("bay_harbor_islands", ("BAY HARBOR", "HARBOR ISLAND")),
        ("bal_harbour", ("BAL HARBOUR", "BAL HARBOR")),
        ("keystone", ("KEYSTONE", "ARCH CREEK", "CORONADO HARBOR")),
        ("miami_beach", ("MIAMI BEACH", "33139", "33140", "33141")),
        ("north_miami", ("NORTH MIAMI", "33181")),
    ]
    for market, needles in rules:
        if any(needle in text for needle in needles):
            return market
    return "unknown"


def is_likely_qualified_sale(sale):
    qual = clean_text(sale.get("qual") or sale.get("qualification") or sale.get("qualified"))
    if not qual:
        return True
    upper = qual.upper()
    bad_tokens = ("UNQUAL", "U -", "U/", "QUIT CLAIM", "CORRECTIVE", "AFFIDAVIT")
    return not any(token in upper for token in bad_tokens)


def city_zip_from_parcel(parcel, default_city, default_zip):
    city = clean_text(parcel.get("city")) or default_city
    zip_code = clean_text(parcel.get("zip") or parcel.get("zipcode") or parcel.get("postalCode"))
    address = clean_text(parcel.get("address"))
    zip_match = re.search(r"\b(33\d{3})\b", address)
    if zip_match:
        zip_code = zip_match.group(1)
    return city, zip_code or default_zip


def normalize_sale_rows(parcel, args):
    address = clean_text(parcel.get("address"))
    folio = clean_text(parcel.get("folio")).replace("-", "")
    legal = clean_text(parcel.get("legal"))
    unit = clean_text(parcel.get("unit")) or infer_unit(address, legal)
    property_class = clean_text(args.property_class) if args.property_class else infer_property_class(parcel, unit)
    if property_class == "condo" and not unit:
        return [], [f"Skipped condo without unit: {address or folio}"]

    city, zip_code = city_zip_from_parcel(parcel, args.default_city, args.default_zip)
    water_type = args.water_type or infer_water_type(parcel)
    condition_class = args.condition_class
    micro_market = args.micro_market or infer_micro_market(parcel)
    living_sf = clean_int(parcel.get("living_sf") or parcel.get("livingSf"))
    lot_sf = clean_int(parcel.get("lot_sf") or parcel.get("lotSf"))
    year_built = clean_int(parcel.get("year_built") or parcel.get("yearBuilt"))
    beds = clean_int(parcel.get("beds"))
    baths = clean_int(parcel.get("baths"))
    subdivision = clean_text(parcel.get("subdivision"))

    rows = []
    skipped = []
    sales_history = parcel.get("sales_history") or parcel.get("salesHistory") or []
    for sale in sales_history:
        sale_date = sale_date_iso(sale.get("date") or sale.get("saleDate"))
        sale_price = clean_int(sale.get("price") or sale.get("salePrice"))
        if not sale_date or not sale_price:
            skipped.append(f"Skipped sale missing date/price: {address or folio} {sale}")
            continue
        if sale_price < args.min_price:
            skipped.append(f"Skipped below min price: {address or folio} {sale_date} {sale_price}")
            continue
        if not args.include_unqualified and not is_likely_qualified_sale(sale):
            skipped.append(f"Skipped likely unqualified sale: {address or folio} {sale_date} {sale.get('qual')}")
            continue

        row_id_base = folio or address_slug(address)
        sale_id = f"pa:{row_id_base}:{sale_date.replace('-', '')}:{sale_price}"
        rows.append({
            "saleId": sale_id,
            "address": address,
            "unit": unit,
            "city": city,
            "zip": zip_code,
            "salePrice": sale_price,
            "saleDate": sale_date,
            "livingSf": living_sf,
            "lotSf": lot_sf,
            "yearBuilt": year_built,
            "beds": beds,
            "baths": baths,
            "propertyClass": property_class,
            "waterType": water_type,
            "conditionClass": condition_class,
            "subdivision": subdivision,
            "microMarket": micro_market,
            "verified": True,
            "source": args.source,
        })
    return rows, skipped


def read_json_or_jsonl(path):
    text = Path(path).read_text()
    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def read_addresses(path):
    source = Path(path)
    if source.suffix.lower() == ".csv":
        with source.open(newline="") as fh:
            reader = csv.DictReader(fh)
            return [row.get("address") or row.get("Address") for row in reader]
    return source.read_text().splitlines()


async def fetch_parcels(addresses):
    from county_pa import fetch_county

    parcels = []
    for address in addresses:
        address = clean_text(address)
        if not address:
            continue
        print(f"Fetching PA record: {address}", flush=True)
        parcel = await fetch_county(address)
        parcel["_query_address"] = address
        parcels.append(parcel)
    return parcels


def write_batches(rows, output_path):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2))

    batch_paths = []
    if len(rows) > SALE_BATCH_LIMIT:
        stem = output.with_suffix("")
        for idx in range(0, len(rows), SALE_BATCH_LIMIT):
            batch = rows[idx:idx + SALE_BATCH_LIMIT]
            batch_path = Path(f"{stem}_batch_{idx // SALE_BATCH_LIMIT + 1:03d}.json")
            batch_path.write_text(json.dumps(batch, indent=2))
            batch_paths.append(batch_path)
    return batch_paths


def push_batches(rows):
    results = []
    for idx in range(0, len(rows), SALE_BATCH_LIMIT):
        batch = rows[idx:idx + SALE_BATCH_LIMIT]
        print(f"Pushing batch {idx // SALE_BATCH_LIMIT + 1}: {len(batch)} rows", flush=True)
        results.append(engine_request("/api/import-sales", {"rows": batch}))
    return results


def build_parser():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pa-json", help="PA parcel JSON/JSONL with sales_history arrays.")
    source.add_argument("--addresses-file", help="Text or CSV file of addresses to fetch from PA.")
    source.add_argument("--address", action="append", help="Address to fetch from PA. Repeatable.")
    parser.add_argument("--out", default="pa_sales_import.json", help="Review JSON output path.")
    parser.add_argument("--push", action="store_true", help="Push rows to /api/import-sales.")
    parser.add_argument("--include-unqualified", action="store_true", help="Include PA sales that look unqualified.")
    parser.add_argument("--min-price", type=int, default=100000, help="Skip sales below this price.")
    parser.add_argument("--default-city", default="Miami Beach")
    parser.add_argument("--default-zip", default="")
    parser.add_argument("--property-class", choices=("sfr", "condo"))
    parser.add_argument("--water-type", choices=sorted(WATER_TYPES))
    parser.add_argument("--condition-class", choices=sorted(CONDITION_CLASSES), default="unknown")
    parser.add_argument("--micro-market")
    parser.add_argument("--source", default="codex_county_pa_sales")
    return parser


async def async_main(args):
    if args.pa_json:
        parcels = read_json_or_jsonl(args.pa_json)
    else:
        addresses = args.address or read_addresses(args.addresses_file)
        parcels = await fetch_parcels(addresses)

    rows = []
    skipped = []
    errored = []
    for parcel in parcels:
        if parcel.get("error"):
            errored.append(parcel)
            continue
        sale_rows, sale_skips = normalize_sale_rows(parcel, args)
        rows.extend(sale_rows)
        skipped.extend(sale_skips)

    deduped = {row["saleId"]: row for row in rows}
    rows = list(deduped.values())
    batch_paths = write_batches(rows, args.out)

    print(f"Parcels read: {len(parcels)}")
    print(f"Rows ready: {len(rows)}")
    print(f"Skipped sales: {len(skipped)}")
    print(f"Errored parcels: {len(errored)}")
    print(f"Wrote: {args.out}")
    for path in batch_paths:
        print(f"Wrote batch: {path}")

    if skipped:
        skipped_path = Path(args.out).with_suffix(".skipped.txt")
        skipped_path.write_text("\n".join(skipped))
        print(f"Wrote skips: {skipped_path}")
    if errored:
        error_path = Path(args.out).with_suffix(".errors.json")
        error_path.write_text(json.dumps(errored, indent=2))
        print(f"Wrote errors: {error_path}")

    if args.push:
        results = push_batches(rows)
        print(json.dumps(results, indent=2))
    else:
        print("Dry run only. Add --push after reviewing the output JSON.")


def main():
    args = build_parser().parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
